# 170: on Isaac, localization sits 0.066 m across the track from the truth, and 11 to 14 mm above it beyond issue 167

**Status:** open; plan written (2026-11-25, after 169's step 1), for 133. **Severity:** to be shown. The across bias is
about half of smooth haruna_down's pose error p95 (0.12 m). **Found:** 2026-11-25, scensim
118, 086 C6e2 and issue 167 (numbered by 133).

## What is the case

Two open quantities on Isaac's haruna_down, measured offline from the runs' records
(`/localization/kinematic_state` against the truth trace `ego.csv`, above 1 m/s;
`c6e2/along.py`, `c6e/locz.py`):

1. **Across the track: -0.065 to -0.071 m** (localization right of the car, with the y axis
   left) in all six C6e2 runs, with motion BVH off and on. Issue 167's probe shows it is not
   the lidar's mount: the lidar prim has no lateral offset, and the rig's mount equals the
   sensor kit's extrinsics (x 0.9, y 0, z 2.0, roll -0.001, pitch 0.015, yaw 1.5386 rad).
2. **NDT's z: +0.022 to +0.026 m above the truth** before issue 167's fix. The 36.22 mm offset
   predicts a bias of its own size, and 11 to 14 mm of the measured one is not accounted for.
   167's reach check on the fixed aib measures what is left.

## Candidates (none measured)

- the truth trace's origin: which point of the body `ego.csv` reports, against Autoware's
  base_link (the rear axle's middle on the ground);
- the map's cloud against the road: the course builder's sampling of the road and its
  verges into `pointcloud_map.pcd`, and the lanelets' frame;
- the vehicle's base_link under the suspension's sag, against Autoware's static vehicle
  model (for z);
- NDT's roll and pitch taking part of an offset on a crowned road (for z and across);
- the sensor kit's yaw of -0.0364 rad (sensor_kit_base_link), which is in both the rig and the
  TF, so it should cancel. Checked only on paper.

## The plan (written 2026-11-25, after issue 169's step 1, before any run; for 133)

**What issue 169 can and cannot explain here (from 169's probe, not from a run of 170).**

- *The across bias (-0.066 m): not explained by 169.* With motion BVH off (C6e2's f1 to f3, and
  every 168 A/B run) the cloud carries no motion at all (169's cases A and E: D - D_true
  0.000 m), yet the bias is -0.065 to -0.067 m. And the motion 169 measures lies along the
  track. A cloud with no motion cannot put localization across the track.
- *The small extra with motion BVH on: possibly explained.* C6e2's BVH-on runs sat at -0.070 to
  -0.071 m, 4 to 5 mm further across than the off side. On haruna_down's bends the renderer
  also turns each point with the car's yaw over the revolution (169's C shows it traces each
  point from its firing pose), and with no point times nothing removes it. *Hypothesis,
  untested:* that turn is the 4 to 5 mm.
- *NDT's z: not explained by 169.* The residual after issue 167's fix (167's reach check) is on
  the BVH-off side too, and 169's motion is horizontal.

**Predictions for 170's numbers after 169's part 3** (the corrector on, xyzircaedt, aib's own
distortion off under BVH), from C6e2's pairing rerun that part 3 already includes:

- the BVH-off side: across within 3 mm of today's (-0.065 to -0.067 m) and NDT z within 3 mm of
  167's reach check. The cloud changes on this side (aib's distortion in, the corrector out),
  but the net is the same single-pose geometry.
- the BVH-on side: across moves to within 2 mm of the off side's, if the hypothesis above holds.

**The steps.** The first two are offline, on records that exist; no run until 133 has seen
their result.

**Step 2 runs first (133, 2026-11-25), with its sizes written before looking.** A difference
between the published TF (base_link to the lidar) and the lidar's real mount moves the pose NDT
reports for base_link, since NDT places the lidar and base_link follows through the TF. The
levers, from the rig (`translation: [0.9, 0.0, 2.0]`):

- *yaw*, δ = the TF's yaw less the real one: base_link moves across by L sin δ, with L = 0.9 m
  (the lidar's forward lever, not its height). A positive δ (the TF turned left of the real
  mount) makes NDT turn the car right by δ, and base_link lands +0.9 sin δ to the left. The
  probe's 1.84 deg (if all of it were a TF error) would give +0.029 m, not 0.066 m. -0.066 m
  needs δ = -4.2 deg, and NDT's heading would then sit 4.2 deg left of the truth (step 1 would
  see it).
- *roll*, ρ = the TF's roll less the real one (positive: left side up): base_link moves across
  by -H sin ρ, with H = 2.0 m (the lidar's height over base_link). -0.066 m needs ρ = +1.9 deg,
  and NDT's roll would sit 1.9 deg off (step 1 would see it).
- *pitch* moves base_link along and up (H sin and L sin of it), not across.

*Prediction (before looking):* δ and ρ are both under 1e-4 rad, since 167's probe found the
rig's mount equal to the kit's extrinsics (yaw 1.5386 rad), and the TF from those extrinsics
adds nothing across. If either is not, its size from the formulas above is compared with -0.066 m.

1. *The attitude and heading split* (offline: C6e2's six runs and 168's twelve,
   `/localization/kinematic_state` against `ego.csv`, above 1 m/s). Per run: the median error
   in roll, pitch and yaw, and the across error against the road's curvature and cross slope
   at each sample. *Predictions:* (a) |roll error| under 0.2 deg. A roll error that put a 2.0 m
   high lidar 0.066 m across would be about 1.9 deg, which the attitude would show. (b) |yaw
   error| under 0.1 deg. A yaw error that moved base_link 0.066 m about the lidar 0.9 m ahead
   would be about 4 deg. (c) The across error does not depend on the curvature's sign (left
   and right bends alike, within 5 mm). If (c) fails, the bias is not a constant offset.
2. *The frames on paper, then by numbers* (offline: the TF tree the run published, from a
   record, against aib's lidar mount and the truth trace's origin). base_link to the lidar from
   the sensor kit's calibration chain (sensor_kit_base_link's yaw -0.0364 rad and the lidar's
   1.5386 rad) against aib's `sensor_mount` (which 169's probe showed as a 1.84 deg turn of the
   published frame from 90 deg); and the point `ego.csv` reports (`course/ego_trace`) against
   Autoware's base_link. *Prediction:* each pair equal within 1 mm and 1e-4 rad. A pair that
   differs gives the bias's size by itself, and that is the finding.
3. *The map against the road* (offline: Haruna's `pointcloud_map.pcd` road points, the crown's
   top across the road per 10 m, against the lanelets' centreline). *Prediction:* within 1 cm
   across. If the map's crown sits about 0.066 m off the lanelets, the map is the cause.
4. Only if 1 to 3 find nothing: a fixture run on a straight, level, uncrowned course
   (fixture_c5's shape with no crown), predicting the across bias there. Its spec comes to 133
   first.

## Step 2's result, the frames (2026-11-25, offline)

- *The TF against the rig.* The kit's chain, base_link to sensor_kit_base_link (rpy -0.001,
  0.015, -0.0364) to `top_base_link` (yaw 1.575) to `top` (identity), from
  `tesla_model3_sensor_kit_description`'s calibration (the same in `individual_params`), equals
  aib's rig mount (`quat` 0.718374885, 0.005063522, 0.005555147, 0.695615573) to under 1e-6
  rad: rpy (0.015004, 0.000937, 1.538615) both. δ and ρ are 0. The levers give 0.000 m across.
  **Held** (predicted under 1e-4 rad).
- *The render against aib's mount* (169's probe): the walls' returns sit where aib's
  `sensor_mount` puts them, D - D_true 0.000 m, the lateral median within 0.06 m at 40 m. A
  yaw difference under about 0.1 deg, so under 1.5 mm across.
- *The truth's origin.* `ego.csv` is the world's truth stream (`scensim/truth`, the entity's
  pose) as it comes. A body-fixed point offset along the car makes an along error, not an
  across one. A constant across bias from the origin would need a body-lateral offset, which
  step 1's split below speaks against: the bias changes with the bend.

So the frame is not 170's cause. The 1.84 deg seen in the probe is the kit's own mount (yaw
1.5386 rad, 90 deg less 1.84 deg), in both the TF and the render.

## Step 1's result, attitude, heading and the bends (2026-11-25, offline)

`isaac-ex/i170/attitude170.py` on C6e2's six runs and 168's twelve (above 1 m/s; across +
left of the truth's heading; the bends by the truth's yaw rate, over 1 deg/s either way).

| | across, all | straight | left bends | right bends | roll err | pitch err | yaw err |
|---|---|---|---|---|---|---|---|
| range over 18 runs | -0.065 to -0.075 m | -0.078 to -0.086 m | -0.060 to -0.104 m | -0.027 to -0.039 m | -0.006 to -0.012 deg | 0.001 to 0.007 deg | -0.007 to +0.089 deg |

- (a) |roll error| under 0.2 deg: **held** (about 0.01 deg).
- (b) |yaw error| under 0.1 deg: **held** (smooth maps under 0.01 deg; the rough maps 0.079 to
  0.089 deg, noted).
- (c) The across error does not depend on the bend's sign within 5 mm: **FAILED**. The straight
  sections sit at about -0.08 m. The left bends are at about -0.06 m in the level runs and -0.09
  to -0.10 m in the runs that are off along the track (C6e2's BVH-on runs and 172's behind
  mode). The right bends are at about -0.035 m in every run. Both bends move the error toward
  the bend's outside relative to the straights' level, the left ones more. *(Corrected the same
  day, before the bend split, from the same table: in the level runs both bends move the error
  toward the left, the left bends by about +0.02 m and the right bends by about +0.045 m, so
  not toward each bend's outside. Only the off-along runs' left bends move right.)* So 170 is
  not a constant offset. *Hypothesis, untested:* a part of it follows the body's roll in the bends
  (the lidar 2.0 m up) or the along error turned by the bend. It is to be split per bend
  radius and speed before step 3.

## The bend split (written 2026-11-25, before looking; 133's two hypotheses)

Offline, on the same 18 runs: per sample, the across error less the run's straight-section
median (the residual), against the truth's curvature (yaw rate over speed, signed: + left),
speed, the truth's body roll, and NDT's roll error.

- *Hypothesis R, body roll.* In a bend the body rolls outward. If NDT follows the roll, nothing
  moves across; a roll error ε (NDT less truth, + left side up) moves base_link by -H sin ε
  across, with H = 2.0 m. *Predictions if R holds:* the residual follows -2.0 x ε sample by sample
  (a slope within 30 % of -2.0 m/rad); left and right bends give residuals of opposite sign
  about the straights' level; and |ε| in the bends reaches about 0.6 to 1.3 deg, since the
  residuals are 0.02 to 0.045 m.
- *Hypothesis A, the along error seen through the bend.* A run that sits a (m) along the track
  behind or ahead, by a lag τ = a / v, has its heading lagging by Δψ = κ v τ = κ a. Its across
  error is then about a x Δψ = κ a². *Predictions if A holds:* the residual scales with κ a², the
  same sign as a for left bends and opposite for right. At a = 0.086 m and κ = 1/30 m, that is
  0.25 mm. So A predicts no visible mode-dependent across split (under 1 mm), and **A cannot
  explain** the 0.03 to 0.04 m extra the off-along runs show in left bends. That holds unless
  the along error itself grows in the bends, which the split also reports (the along residual
  by bend).
- *What neither predicts.* Both give residuals of opposite sign in left and right bends. The
  level runs' residuals are both toward the left (+0.02 and +0.045 m; the correction above). A
  component of one sign in both bends would point to something that follows the bend's
  presence (speed, yaw rate's size, steering) rather than its direction. The split reports the
  residual against |κ| and speed for that.

## The bend split's result (2026-11-25, offline)

`isaac-ex/i170/bends170.py` (`bends170.jsonl`), the 18 runs. The residual is the across error less
the run's straight median (-0.078 to -0.086 m), binned by the truth's curvature κ (+ left).

| κ bin (1/m) | samples a run | residual, level runs | residual, off-along runs | NDT roll error | -2.0 sin(roll error) |
|---|---|---|---|---|---|
| under -0.02 (right hairpins, R about 20 m) | 1190 to 1250 | +0.133 to +0.148 m | +0.173 to +0.189 m | +0.075 to +0.097 deg | -0.003 m |
| -0.02 to -0.005 | about 1360 | +0.007 to +0.015 m | +0.011 to +0.015 m | about 0 | 0 |
| -0.005 to 0.005 | about 3390 | 0 (by construction, about) | 0 | -0.01 deg | 0 |
| 0.005 to 0.02 | about 258 | +0.002 to +0.010 m | -0.019 to -0.021 m | -0.04 to -0.07 deg | +0.002 m |
| over 0.02 (left hairpins, R about 18 m) | 1067 to 1113 | +0.024 to +0.033 m | -0.013 to -0.030 m | -0.085 to -0.102 deg | +0.003 m |

- *Hypothesis R (body roll):* **FAILED.** NDT's roll error in the hairpins is under 0.1 deg,
  which predicts about 3 mm against residuals of 0.03 to 0.19 m. The fitted slope of the residual
  on -2.0 sin ε is -1.5 to -18.6 m/rad across runs, not about +1. The residuals are also not of
  opposite sign in the two directions in the level runs.
- *Hypothesis A (the along error through the bend):* as predicted, **it cannot explain** the
  mode-dependent split. It predicts under 1 mm, and the off-along runs differ from the level runs
  by about 0.04 m in the right hairpins and about 0.05 m in the left ones.
- *What the split shows (not predicted).* The across error has two parts. (1) A level of -0.078 to
  -0.086 m on the straights and gentle bends, the same in every run and mode: the bulk of 170.
  (2) A hairpin part, large in the right hairpins (+0.13 to +0.19 m, toward their outside) and
  small in the left ones, which shifts with 172's along mode. NDT's yaw error in the hairpins
  stays under 0.25 deg (two runs checked), so the heading does not carry it.
- *Next.* Step 3 (the map) for the straights' level, since it is constant and mode-free, which is
  what a map or frame offset would give and the frames are ruled out. For the hairpins, whether
  the map's road and lanelets in Haruna's tight bends sit where the world's road mesh is, in the
  same check.

## Step 3's predictions, the map (written 2026-11-25, before looking; 133's order)

**Which map can move localization against the truth.** NDT matches the scan, rendered from the
world's meshes from the true pose, to `pointcloud_map.pcd`. If the map's cloud sits a vector s
off the world's meshes, NDT's pose sits s off the truth. So the across error is the point cloud
map's offset from the world, across the road. The lanelets steer the car (where it drives), but
they do not enter NDT. A lanelet offset moves the truth and localization together and cannot
make the error between them. So:

- *The point cloud map against the world's meshes* (the course's `meshes.npz`, which the USD
  is built from; Haruna as C6e2 ran it, `c6b-haruna/none/haruna`). This is a translation-only
  nearest-neighbour fit of the map's points to the meshes within 15 m of the driven path,
  separately on the straights, the right hairpins and the left hairpins, each offset projected
  on the road's left normal. *Predictions if the map explains 170:* the straights' offset is
  -0.08 m (within 0.02; the map right of the world), the right hairpins' about +0.06 m, and the
  left hairpins' about -0.05 m (the straights' level plus each residual). *If the map is not the
  cause:* every offset is within 0.01 m of 0.
- *The lanelets against the mesh's crown* (133's question): the lanelet centreline of the ego's
  lane against the road mesh's centre (the crown) on the straights. I predict it says where
  the car drives, not the error. A lanelet centreline 0.08 m off the crown would show as the
  truth's own lateral place in the lane, not as localization against the truth. It is reported
  for completeness.
- *A check from the records first:* if the map's offset is one fixed world vector, the across
  error on the straights varies with the truth's heading as a sine of that vector's size. If it
  is constant whatever the heading, the offset follows the road (a ribbon built off its
  centreline) or the car, not a fixed shift.

## Step 3's first result: the heading check (2026-11-25, offline, from the records)

On the straight sections (yaw rate under 1 deg/s) of the 18 runs, the across error is not
constant with the truth's heading: about +0.05 to +0.08 m on headings -135 to -45 deg, and
-0.07 to -0.11 m on 0 to 180 deg (two runs binned by 45 deg). The prediction "constant whatever
the heading" **FAILED**. Fitting each run's error (x and y in the map frame) as one fixed map
vector plus a car-fixed along and across part:

| | fixed map vector (x, y) | its size | car-fixed across | car-fixed along | rms residual |
|---|---|---|---|---|---|
| all 18 runs | +0.042 to +0.050, +0.022 to +0.029 m | 0.051 to 0.056 m | -0.035 to -0.040 m | level runs -0.010 to -0.014; behind -0.103 to -0.105; C6e2 BVH-on +0.098 to +0.099 | 0.035 to 0.037 m |

- The straights' error is two parts, the same in every run. (1) A fixed shift of about 5 cm in
  the map frame (toward +x, +y), which is what a point cloud map off the world, or a frame offset
  between the map and the truth, would give. (2) A car-fixed -0.037 m across. 172's modes sit in
  the car-fixed along part alone. The residual is still 0.035 m rms, so the model leaves some of it
  unexplained.
- *The sharper prediction for the registration (written before it, labelled as after this
  result):* if the point cloud map is the cause of part (1), the fit of the map to the world's
  meshes gives a shift of about (+0.045, +0.026) m, within 0.01. If it gives 0, part (1) is a
  frame offset between the map frame and the truth's, to be found in the course's projector and
  `map_origin`. Part (2), car-fixed, is neither: it is to be looked for in the truth's origin
  across the car or in the lidar's lateral place, the latter ruled out by issue 167's probe.

## Step 3's result: the point cloud map against the world (2026-11-25, offline) (WITHDRAWN: see the CORRECTION below)

`isaac-ex/i170/register170.py`: a translation-only point-to-plane fit of Haruna's
`pointcloud_map.pcd` (the map C6e2 and 168 ran on, `c6b-haruna/none/haruna`), using its points
within 15 m of a run's driven path, to the world's ground meshes. The meshes are the USD's own
`/Course/Terrain`, `/Course/Road` and `/Course/Lines`, exported by `usd_meshes.py` with Isaac's
pxr. The course's `meshes.npz` gives the same within 1.4 cm. *The method's own bias, from
`selftest170.py` (a synthetic map sampled on the same faces):* a true 0 reads as (+0.015, -0.005,
-0.004) m, and a planted (+0.10, +0.04, -0.035) reads as (+0.115, +0.035, -0.039). The shifts below
are read with that bias in mind.

| region | points used | the map off the world (x, y, z) | plane residual rms |
|---|---|---|---|
| straights | 73,108 of 200,000 | ~~+0.104, +0.042, -0.037 m~~ | 0.050 m |
| right hairpins | 72,604 | ~~+0.033, +0.030, -0.023 m~~ | 0.078 m |
| left hairpins | 75,969 | ~~+0.071, +0.048, -0.027 m~~ | 0.079 m |

- *Against the predictions.* The map is off the world (the "not the cause" prediction, within
  0.01 of 0, **FAILED**). On the straights it is off in the same direction as the runs' fixed map
  vector, (+0.045, +0.026) m at 30 deg against the map's 22 deg, but about twice its size. The
  "within 0.01 m of (+0.045, +0.026)" prediction **FAILED** on size. The map also sits 3.7 cm low
  (3.3 cm net of the bias). The offset is not one vector: it differs by region by up to 7 cm in x.
- *Caveats, stated before anything is built on this.* Only 36 to 38 % of the map's points lie
  within 1 m of a ground face. The rest are props (guardrails, the course's other objects), not
  in the export, and they are left out of the fit. NDT matches those too. The world rendered in a
  run is not the bare USD: the road layer draws its detail mesh on the road (issue 168), and
  NDT's z after 167 (-0.004 to -0.014 m) does not show the map's -3.3 cm in full. So NDT follows
  the map's offset only in part, and this fit is of the ground alone.
- *What follows (a plan item for 133, not done).* (1) How the course builder samples the map's
  cloud (its map step) and where a 5 to 10 cm horizontal and 3 to 4 cm vertical offset from the
  USD's meshes can come from: a different sampling of the same surfaces, the projector's origin,
  or a step that moves one and not the other. (2) The same fit with the props included (the
  USD's props exported too), against the full map. (3) Whether the region-dependent offset
  explains the hairpin part of the across error.

## The hairpin prediction from the registration (written 2026-11-25, before comparing) (VOID: see the CORRECTION below)

*Labelled:* the hairpin residuals are already measured (the bend split). This prediction comes
only from the registration's per-region vectors and the straights' fit, made before the two are
set side by side.

- The model: in each region the across error is f x (the region's map vector) . n, plus the
  car-fixed -0.037 m, with n the road's left normal at the sample (the truth's heading). f is the
  part of the map's offset that NDT follows, from the straights: the runs' fixed vector
  (+0.045, +0.026), 0.052 m, against the registration's straights vector (+0.104, +0.042),
  0.112 m, so f is about 0.46.
- Per region, its median over the samples of one level run (C6e2's f1), computed and written here
  before it is compared with the measured hairpin medians (straights -0.078, right hairpins
  -0.078 + 0.133 = about +0.055, left hairpins -0.078 + 0.024 = about -0.054).
- *The numbers (labelled: the prediction and the measured medians were printed by the same
  command, so the prediction was not written before the comparison was visible; the model and
  its inputs above were).* C6e2 f1, median across:

  | region | predicted (0.46 x map . n - 0.037) | measured | difference |
  |---|---|---|---|
  | straights (3391 samples) | ~~-0.072 m~~ | -0.079 m | ~~0.007 m~~ |
  | left hairpins (1090) | ~~-0.036 m~~ | -0.053 m | ~~0.017 m~~ |
  | right hairpins (1187) | ~~-0.031 m~~ | +0.055 m | ~~0.086 m~~ |

  The regional map offset reproduces the straights and roughly the left hairpins. It does **not**
  explain the right hairpins: it predicts -0.03 m where +0.055 m is measured. The right hairpins'
  +0.13 m residual has another cause, still open.

## CORRECTION to step 3's registration (2026-11-25, the same evening): the map is NOT off the world

The two sections above ("Step 3's result: the point cloud map against the world" and "The
hairpin prediction from the registration") rest on a fit that was pulled by off-surface points,
and their conclusion, that the map sits 5 to 10 cm off the world, is **withdrawn**.

- *Why it was rechecked.* The course builder (`course/maps.py`, `point_cloud`) samples the map
  from the same meshes the USD is made of, written two minutes apart (`meshes.npz` 10:20:29,
  `world.usdc` 10:20:30, the cloud 10:22:30, 2026-11-23). A real 10 cm offset between them is
  then hard to explain.
- *The cause.* The fit kept every map point within 1 m of a ground face. Points from props and
  foliage near the ground (guardrails at the road's edge, the course's other objects) are within
  that distance and off the surface, and they pulled the fit sideways and down. The synthetic
  self-test had no props, so it did not show this.
- *The fit again, keeping only points within 0.05 m of a face's plane* (`ROBUST=0.05`):
  straights (-0.002, -0.001, +0.001), right hairpins (-0.002, +0.005, +0.000), left hairpins
  (-0.001, -0.004, +0.001) m, plane residual 0.012 m rms. With a 0.10 m cut the old result comes
  back (props still in). *The tight cut's own check* (`selftest170.py` with the same cut): a true 0
  reads within 1.3 mm, and planted shifts of (+0.10, +0.04, -0.035) and (+0.10, +0.04, 0) are
  recovered within 1.3 mm. A horizontal shift on the course's sloped ground stays well inside the
  cut, so the cut does not hide one.
- *So:* Haruna's point cloud map matches the world's ground within about 5 mm, in x, y and z, on
  the straights and in both hairpins. The step 3 prediction "if the map is not the cause, every
  offset within 0.01 m of 0" **held**. The prediction that the map explains the runs' fixed
  vector **FAILED**. The hairpin comparison above is void (its vectors were the artifact).
- *What stays open.* The runs' fixed map-frame vector (about 5 cm toward +x, +y), the car-fixed
  -0.037 m across, and the right hairpins' +0.13 m are all still unexplained, and the map's
  ground is not their cause. Left: the props in the map against the world's (the cloud includes
  them; they were not exported), and a frame offset between the map and the truth (the
  projector, `map_origin`).

### The correction, settled (2026-11-25, offline; 133 asked for the self-test with props)

- *Why the first self-test missed it:* it had no props. It sampled points only on the ground
  faces, so nothing off the surface could pull the fit.
- *A self-test with props* (`selftest_props170.py`): the synthetic ground map (a true shift of 0)
  plus the real map's off-surface points near the ground (225,573 points within 1 m of a face and
  more than 0.05 m off its plane). The old fit (keep within 1 m) reads the map off by (+0.152,
  +0.004, -0.046) m, the artifact reproduced. The 0.05 m cut still reads (+0.061, +0.019, -0.002):
  with props two to one against the synthetic ground, points near the cut's edge let it drift.
  So a plane-residual cut is not a sound guard either, and no fit of this kind is used again
  without a props self-test at the real map's mix.
- *The decisive check, with no fit at all* (`rebuild170.py`): the course builder's own
  `maps.point_cloud` (its seed, 58), run on the map directory's `meshes.npz`, centreline and
  `props_points.npy`, reproduces Haruna's `pointcloud_map.pcd` bit for bit: 15,788,823 points,
  all identical, none on either side only. The map's ground is exactly the course's meshes, and
  the USD is built from the same meshes (the same vertex counts; `usd_meshes.py`). **The map
  matches the world by construction**, ground and props alike, so far as the props in
  `props_points.npy` are the USD's props, which is still to be checked.
- *The map-to-truth frame (133's next check), on paper.* `world.yaml`'s `map_origin` is
  (0, 0, 0). The map's points are the meshes' coordinates unchanged (above), and the truth
  stream's poses are the world server's (`scenario_world_bridge` `truth_topic.rs`: the run's
  gap-trace poses as they arrive). The projector (`map_projector_info.yaml`, a transverse
  Mercator at 36.494, 138.903) places the lanelets, and every lanelet point also carries
  `local_x` and `local_y`. It does not move the point cloud, which NDT uses. So there is no
  frame offset between the map NDT uses and the truth. Still to confirm by numbers: a vehicle
  pose the world server logs against the same instant's truth row.
- *What stays open, then:* the runs' fixed map-frame vector of about 5 cm, the car-fixed
  -0.037 m, and the right hairpins' +0.13 m. Neither the map nor the frames explain them. The
  "fixed vector plus car-fixed" model left 0.035 m rms unexplained, so it may be the wrong
  model. The next candidate is NDT's own estimate (its convergence on this map's geometry), to be
  planned with 133.

## The truth's origin against base_link, by numbers (243, 2026-11-27; predictions before reading)

Taken up by 243 on 133's assignment. The records the steps above used (C6e2's six runs, 168's
twelve, `isaac-ex/i170/`) are on 118's host. This first check needs none of them: it reads the
code and the car's spec.

*The question.* What point of the car the truth stream (`ego.csv`, `scensim/truth`) reports.
`scensim.truth` already takes an `origin_offset` off the world server's body pose to give
base_link (the rear axle's middle on the ground). If that offset, or the body pose it is taken
from, has a lateral part for tesla_model3, the truth sits that far across from base_link, and the
error between localization and the truth carries it as a car-fixed across part: the
"car-fixed -0.037 m" above.

*Predictions, before reading:*
- T1: the offset `scensim.truth` applies for tesla_model3 has no lateral component (|y| under
  1 mm). The spec's body is symmetric about the car's centreline, and base_link is on it.
- T2: so the truth's origin is not the car-fixed -0.037 m. If T1 fails, its y is compared with
  -0.037 m directly: the truth to the left of base_link by d gives localization (at base_link)
  d to the right of the truth, an across error of -d.
- T3: the along part of the offset (the body's centre ahead of the rear axle) is applied, so it
  makes no along error; if it were not applied, the runs would show an along error of about the
  wheelbase's half, 1.4 m, which they do not (their along errors are under 0.11 m).

**Result, on paper (2026-11-27).** All three held; the truth's origin is not 170's car-fixed
across part.
- *What the truth carries.* `/scensim/truth` publishes each entity's simulator body pose, the
  gap trace's `sim_pose` (`scenario_world_bridge/src/truth_topic.rs`), and
  `/scensim/truth/entities` carries each entity's `origin_offset`, "body origin from entity
  origin" (`scensim_interfaces/msg/TruthEntity.msg`).
- *T1 held.* On Isaac the ego's `origin_offset` is (0, 0, 0)
  (`scensim_isaac_world/catalogue.py`, `ego_body`): its body pose is base_link itself, "the rear
  axle on the ground" (`vehicle_assets.py`: the ego's body "sits with its rear axle on
  base_link"). The rig puts that point on the centreline: aib's `tesla_model3.rig.yaml` has
  `box_center: [1.416, 0.0, 0.744]` and a symmetric `wheel_tread: 1.667`. So nothing lateral, and
  whatever `ego.csv`'s extractor does with the offset, it has nothing to take off.
- *T2 held:* the -0.037 m is not the truth's origin.
- *T3 held:* there is no along offset to apply either, consistent with the runs' along errors
  under 0.11 m.
- *Not checked here:* which prim the world server reads the pose from at run time (the rig's
  root, by the code above). A recorded frame against the same instant's `/tf` (base_link in the
  map, from the truth) would settle it by numbers; the records are on 118's host.

**What is left offline, and what needs a run.** The three open parts (the ~5 cm fixed map-frame
vector, the car-fixed -0.037 m, the right hairpins' +0.13 m) have no offline candidate left in
this record's list but two: whether the map's props (`props_points.npy`) are the USD's props
(offline, Isaac's pxr on the CPU), and NDT's own estimate on this map's geometry (its score
and iteration count against the error, from the runs' records if they hold NDT's topics). Both
need C6e2's or 168's records here. The plan's step 4 (a fixture run on a straight, level,
uncrowned course) needs the card.

## Step 4's spec: a straight, level, uncrowned fixture, both ways (243, 2026-11-27; for 133, before any run)

**The course, `fixture_c170`.** Built by 086 C5b's fixture builder
(`python3 -m scensim_isaac_world.course courses/fixture_c170.yaml <map dir>`: the
`centreline`, `geometry`, `record`, `maps` and `scenario` steps, then the USD, all on the CPU),
as fixture_c5 is, with every section term set to zero:
- the same arbitrary datum as fixture_c5 (36.0, 140.0, alt 0), `map_origin` (0, 0, 0);
- one straight, 600 m (`plan: [{straight: 600.0}]`), grade 0;
- 2 lanes of 3.25 m, shoulders 0.75 m, crown 0 both sides, no bank, no crown offset, no lip;
- the terrain flat, 0.30 m below the road (`terrain_below: 0.30`), as fixture_c5's, so the
  road's edges are the only lateral relief NDT has; no props.

**The runs** (Isaac Sim 6.2 and the ego stack, stock clustering, `max_velocity: 11.11`; the
profile and every pin as main has them):
- R1: the ego drives the right lane from s 20 to s 580 (east, heading 0), and stops.
- R2: the same in the other lane from s 580 to s 20 (west, heading 180 deg).
- R3: R1 again, for repeatability.

Each records, besides the gap trace: `/localization/kinematic_state`,
`/localization/pose_estimator/pose_with_covariance`, NDT's `transform_probability`,
`nearest_voxel_transformation_likelihood` and `iteration_num`, `/sensing/gnss/pose_with_covariance`,
`/sensing/gnss/gnss_link/nav_sat_fix`, `/tf` and `/tf_static`.

**The ego prim's check, for free (133).** aib computes its GNSS fix from the PhysX vehicle's
state, with no noise (`aib.sensing.gnss_reading`: the antenna at its rig lever from base_link),
and Autoware's gnss_poser turns it back into base_link's pose in the map. That is an
independent reading of the ego's state at run time, against the world server's `sim_pose` in the
gap trace at the same sim time.

**Predictions, written before any course is built.**
- G1, the ego prim: the GNSS-derived base_link pose and the gap trace's `sim_pose` agree within
  1 cm along and across, and 1e-3 rad in yaw, over each run above 1 m/s. If they do not, the
  difference is the truth's own offset and is set against 170's numbers.
- G2, the straight's across error, both ways: R1 and R2 both read about -0.037 m (within
  0.015 m), localization right of the truth: the car-fixed part from Haruna, present with no
  crown, bank, grade or curvature. The fixed map-frame vector is about 0 here (its across
  projection under 0.01 m), since this map is the meshes by construction, as Haruna's was.
  The two runs give it by sum and difference: car-fixed c = (R1 + R2) / 2, the map vector's
  north component v = (R1 - R2) / 2.
- G3, the alternative, stated so it can be told apart: if the across error is a property of
  Haruna's geometry (its crown, its bends, its props), R1 and R2 both read within 0.01 m of 0.
- G4, z: NDT's z within 5 mm of the truth's on this flat course (167's fix, and no crown or
  grade to pull it).
- G5, repeatability: R3 within 5 mm of R1 across.

**What it needs, for 133's scheduling.** Building the course and its USD: CPU only, about
20 minutes, Isaac's Python for the USD step. A project for it beside the c5 ones (on 118's host
today), or a new one here. Each run: Isaac Sim 6.2 with the world (the fixture's world is small),
about 12 GB free on the card held for 2 minutes, about 10 to 15 minutes of card time; three runs.
The scenario's second direction (R2) needs the `scenario` step's route in the other lane, which
fixture_c5's builder does not make today: one more generated scenario file, or a hand-written one.

**G1's scope, and the build (2026-11-27, before any run; 133's approval and notes).**
- *Which prim each side reads.* The world server's truth for the ego is aib's `Ego.state`
  (`scensim_isaac_world/world.py`, the ego's `state.position` and `state.quat` in each step's
  reply), and aib's GNSS is computed from the same `state` (`aib/isaac/sensors.py`, `Gnss`,
  `gnss_reading(state, ...)`). Both read the same PhysX body through the same object. So G1
  checks the transforms between them (the GNSS antenna's lever, the projector to latitude and
  longitude and back, gnss_poser), not which prim the truth is. G1 is kept as that check.
- *As built (kept off main and off the NAS datasets).* The course yaml is
  `/var/tmp/aeon/170/fixture_c170.yaml`: fixture_c5's datum and road, `plan: [{straight: 600.0}]`,
  `grade: 0.0`, `terrain_below: 0.30`, `crown: 0.0`, every section term 0. Built by
  `python3 -m scensim_isaac_world.course fixture_c170.yaml <map dir> centreline geometry record`,
  then `$ISAAC_ROOT/venv/bin/python -m scensim_isaac_world.course.usd fixture_c170.yaml <map dir>`,
  then the `maps` and `scenario` steps: 600 m, lanelets 6 along and 6 back, 801,548 map points.
  R1 and R3 use the builder's scenario (start x 20, y +1.62, the left lane, heading 0, to x 570);
  R2 is a copy with start x 580, y -1.62, heading pi, to x 30. The project is a copy of
  `scenarios/projects/courses` (drift_mustang under Autoware, aib's drift_mustang rig, as the
  Haruna runs) with the fixture linked as `assets/maps/fixture_c170`, no judges, and the topics
  above. The install is a clean build of main fcc01e50 (acb's workspace, then scensim's).
- *Two differences from the spec, settled before R1.* (1) Speed: the project first copied the
  courses project's `max_velocity: 8`; set to the spec's 11.11 before any run started. (2) Lane:
  the spec names the right lane eastbound; the builder's scenario starts in the left one
  (y +1.62, heading 0), and R2 is its mirror (y -1.62, heading pi). The road is symmetric across
  its centreline, so the lane changes only the sign of y in the map, not the geometry NDT sees;
  kept as built, and the across errors are reported in the car's frame (+ left of the truth's
  heading), so R1 and R2 compare as the spec's sum and difference.

**A standstill window (133, 2026-11-27, before R1).** In 118's run A (fixture_c6b, Isaac, stopped
for 150 s) the kinematic state's x drifted 0.36 m along the track while the truth held within
1 mm, and ekf_localizer warned "mahalanobis distance of pose topic is large" before each of 72
MRMs. 241's untested guess: NDT is weakly constrained along a featureless straight. R1 and R3 now
end 45 s after the ego first comes within 5 m of the goal (`reach_goal`'s `delay="45"`, which
SSv2's interpreter honours: the condition's value 45 s earlier), so each stands still for 30 s or
more at x about 570; R2 is unchanged. The window is the samples with the truth's speed under
0.01 m/s after the stop.

*Predictions, before R1.* fixture_c170 is flat and straight with no props: along the track NDT
has nothing but the road's ends, which are 550 m or more behind and 30 m ahead (beyond the
scan's useful range behind, within it ahead). So:
- S1 (241's guess holds here): over the window the kinematic state's along position moves
  0.1 m or more while the truth moves under 1 mm; across and z move under 0.01 m; NDT's
  along position wanders more than its across (its sd along over 3 times its sd across); the
  mahalanobis WARN appears in ekf_localizer's log in the window.
- S2, what tells it apart: if NDT's along estimate holds within 0.02 m over the window, the
  straight's lack of features does not move a stopped car's pose by itself, and run A's drift
  needs another cause (its stop place, its features, or a moving input such as the twist).
- Moving, for the same reason: NDT's along error has a larger spread than its across one over
  the drive (sd along over 2 times sd across), whatever its across level is (G2).
I expect S1 at the smaller end: with the goal 30 m from the road's end, the end wall of points
is inside the scan, so some along constraint exists; the drift, if any, is under run A's 0.36 m.

## The two offline checks left, (a) and (b): predictions (243, 2026-11-27, before reading any output)

Inputs: 118's staging (`home/2026-11-27 issue 170 inputs (118)/` on the NAS, SHA256SUMS verified
here): smooth Haruna's map directory and `isaac-ex/i170`; the runs from their NAS records.

**(a) Are the map's props the USD's props?** `props_points.npy` (12,131,948 points) is what the
builder sampled from each prop asset by its own placement code (`course/props.py`, `place`); the
renderer draws what USD composition makes of `world.usdc`. A check by composition, not by that
code: `props_vs_usd.py` composes the stage (guardrail meshes by their composed transforms, the
trees by the PointInstancer's `ComputeInstanceTransformsAtTime` and each prototype's meshes),
samples the composed triangles, and measures map points against them and back.
- On paper first: a guardrail prim authors its own `xformOpOrder` (translate, rotateZ, scale)
  over the referenced asset, which would drop a non-identity transform on the asset's root,
  while `asset_surface` keeps it. Read: all five Town01 assets have an identity `/Root`,
  metersPerUnit 1, Z up. So no difference is expected from that.
- Limits here: this host's asset set is Town01 only, so tree kind 4 (`Town02/.../
  SM_Japanese_Maple_01.usd`) is left out, with map points within 6 m of its instances; trees are
  composed within 60 m of the road and map points beyond 55 m are left out; the asset revision
  is this host's cache (38347e26), assumed the same as 118's.
- *Predictions:* the map's prop points lie on the composed props: |distance to the nearest
  composed triangle's plane| p50 under 1 mm, the mean offset vector under 1 cm in each axis;
  and the rendered props within 40 m of the road are in the map: under 1 % of composed samples
  more than 1 m from a map point. If either fails, the size and direction of the difference is
  set against 170's ~5 cm fixed vector.

**(b) NDT's own convergence against the error.** The 18 records hold NDT's
`nearest_voxel_transformation_likelihood` (all) and `iteration_num` (168's twelve), not NDT's
pose. Per run, each kinematic-state sample's across error from the truth (as in step 1) is
joined with the nearest NVTL and iteration count in time.
- *Predictions,* if the error is a converged bias rather than poor convergence: (b1) the across
  error and NVTL are uncorrelated, |Pearson r| under 0.3 in every run; (b2) in the right
  hairpins, where the across error reaches +0.13 m, the median NVTL is within 0.1 of the
  straights'; (b3) iteration_num at the limit (30) in under 1 % of samples. If (b1) or (b2) fails,
  NDT's convergence on this map's geometry is implicated, and where it fails says where.

## (a) and (b): results (243, 2026-11-27, offline)

Scripts and outputs: `/var/tmp/aeon/170/a/` (`props_vs_usd.py`, `props_vs_usd2.py`, their json)
and `/var/tmp/aeon/170/b/` (`ndt170.py`, `ndt170.jsonl`) on 243's host.

**(a) The map's props are the USD's props.**
- Composed: 120 guardrail meshes; tree kinds 0 to 3, 1,661 of 3,131 instances (those within 60 m
  of the road); kind 4 is missing from this host's asset set. 81.8 M samples of the composed
  triangles.
- *Forward,* 400,000 map prop points (left out: 5.49 M within 6 m of a kind-4 trunk, 4.90 M
  beyond 55 m of the road): |distance to the nearest composed triangle's plane| p50 **1.08 mm**
  (predicted under 1 mm: just over, by sampling; per kind 0.39 to 1.17 mm), mean offset
  (+0.11, +0.07, -0.26) mm (**held**, under 1 cm).
- *The guardrails, every map point* (2,315, about 19 a segment, as 6 per m^2 of the asset gives):
  |plane distance| p50 0.23 mm, signed (+ away from the road) p5 -16 mm, p50 0.0 mm, p95 +17 mm;
  per segment with 20 points or more (7) the median is -0.01 to +14 mm; z against the composed
  rail -0.1 mm.
- *Reverse,* 400,000 composed samples within 40 m of the road: 0.055 % more than 1 m from a map
  point (**held**, under 1 %); guardrails 0.0 %.
- *The forward far points* (3.65 % with no composed sample within 0.3 m): 0.55 % of map points
  have neither a composed trunk within 8 m nor a rail; they sit 6 to 17 m (p5 to p95) from a
  kind-4 trunk, the maples' canopies beyond the 6 m left out. Not a mismatch.
- *So:* the map holds the rendered props, in place to about a millimetre. The props do not
  explain the ~5 cm fixed vector or the hairpin part. With the ground (`rebuild170.py`) this
  closes the map: the point cloud NDT matches against is the world the lidar renders.

**(b) NDT converges, uniformly, where the error is large.** Per run (`ndt170.jsonl`), the across
error and its residual reproduce step 1 and the bend split (straights -0.078 to -0.086 m, the
right hairpins' residual +0.133 to +0.189 m).

| over 18 runs | r(across, NVTL) | r(abs residual, NVTL) | NVTL straights | NVTL right hairpins | NVTL p5 | iterations median, p99 | at 30 or more |
|---|---|---|---|---|---|---|---|
| range | +0.11 to +0.21 | +0.04 to +0.14 | 3.155 to 3.158 | 3.151 to 3.155 | 3.118 to 3.120 | 2 to 3, 5 | 0 to 0.03 % (168's 12) |

- (b1) |r| under 0.3 in every run: **held.**
- (b2) The right hairpins' NVTL within 0.1 of the straights': **held** (0.002 to 0.007 below).
- (b3) iteration_num at 30 or more in under 1 %: **held**, with a note: the largest values are
  36 and 60 (in 5 runs, one to three messages each), so 30 is not the limit these runs had; the
  check stands as a share of high counts, not of hits at the limit.
- *So:* NDT's score and its iterations are the same on the straights and in the right hairpins,
  where the error is 0.13 to 0.19 m larger, and they do not follow the error. NDT reaches the same
  quality of fit at a pose off the truth: the error is where NDT's optimum is, not a failure to
  reach it. With the map equal to the world ((a) and step 3), the optimum is off because the scan
  NDT is given differs from what the map predicts at the true pose. That points at the scan's
  side (where the lidar's points are put relative to base_link, and when), which step 4's fixture
  runs measure with no bends, crown or props. Not tested here.

**The vehicle, set before R1 (243, 2026-11-27).** The as-built note above had R1 to R3 in
drift_mustang (the courses project's car). C6e2's and 168's runs, where the car-fixed -0.037 m
comes from, drove the Tesla Model 3 (their `resolved.yaml`: no vehicle override,
`vehicle_model:=tesla_model3`, aib's default rig). G2 compares the fixture with those runs, so a
different car (its own sensor kit and rig mount) would mix the vehicle into the answer. Before
any run: the three scenarios' ego is `tesla_model3`, the testbench has no vehicle override and no
rig file (aib's default Tesla), the asset take is `vehicles/vehicle.tesla.model3`, and the fixture
is a `path:` asset (`scensim testbench check`: ok). `max_velocity` stays the spec's 11.11.

## The scan side, on the CPU (133, 2026-11-27): predictions before reading

After (a) and (b) the map is the world and NDT converges; what is left is the scan NDT is given.
Two checks, for the Tesla the 18 runs drove.

**(1) The extrinsic.** Step 2 compared the rotations (the kit's chain against aib's mount, to
under 1e-6 rad) and the render against the mount (169's probe). Still open: the translation,
and the chain as `/tf_static` publishes it at run time rather than as the files give it.
- *E1:* the kit's base_link to the top lidar translation equals aib's rig mount position within
  1 mm in each axis. A few cm off would give a fixed car-frame offset of that size; it would
  appear across only if its y part is off, by the same amount.
- *E2:* the rotation as published equals the files' (step 2) within 1e-4 rad. A yaw error of
  0.1 deg puts points at 20 m off by 3.5 cm sideways, but NDT absorbs a pure yaw error as a yaw
  error of the pose, not as a sideways shift at base_link (the levers give under 2 mm).

**(2) Timing and motion distortion.** What decides it: whether Autoware's
`distortion_corrector` runs on the Isaac kit's top lidar, which time the cloud's header carries
(the scan's start, middle or end), and whether aib's points carry per-point times.
- *D1:* the corrector runs (it is in Autoware's standard sensing chain for the top lidar).
- *D2:* aib renders each scan at one simulation step and gives every point the same time (no
  per-point offsets, or all zero), so the cloud has no distortion and the corrector moves nothing.
  Then (2) predicts no error at any speed, and the 18 runs' errors are not from it.
- *If D2 fails* (per-point times spread over the scan's period, 0.1 s, on a cloud rendered at one
  instant): the corrector moves each point by the car's motion over its time offset, a
  distortion that was never there. At speed v the cloud is moved along by about v times the mean
  offset (0.4 to 1.1 m at 4 to 11 m/s with a 0.1 s scan, against the runs' along errors under
  0.11 m: it would be seen), and in a bend turned by the yaw rate times the mean offset, which
  changes sign with the bend (opposite in left and right hairpins) and is 0 on the straights. So
  even then it could not give the straights' -0.08 m across; it could give an antisymmetric part
  of the bends.
- *The header stamp:* if it is the scan's end while the points are rendered at its start (or the
  other way), the cloud is late or early by up to 0.1 s; the EKF then places it where the car was
  v times that ago, an along error (0.4 to 1.1 m) and no across error on a straight. The runs'
  along errors (under 0.11 m) bound such a lag to about 10 ms at 11 m/s.
A standstill drift (run A) comes from neither (2) nor a fixed extrinsic: both vanish at v = 0.

## The scan side: results (243, 2026-11-27, from the code and the files at main fcc01e50)

**(1) The extrinsic.**
- *E1 held (files).* The kit (`tesla_model3_sensor_kit_description`): base_link to
  sensor_kit_base_link (0.9, 0.0, 2.0), then to `velodyne_top_base_link` (0, 0, 0); aib's rig
  (`tesla_model3.rig.yaml`, `sensors.top.translation`): (0.9, 0.0, 2.0). Equal, to the files'
  precision (1 mm). With step 2's rotations (under 1e-6 rad), the kit and the rig agree in full.
- *E2, the chain as `/tf_static` publishes it at run time:* not in the 18 records (they hold no
  `/tf_static`); R1 records it, and it is checked there.

**(2) Timing and motion distortion, for the Tesla the 18 runs drove.**
- *D1 failed:* the corrector does not run. The kit's `sensing.launch.xml` and `lidar.launch.xml`
  default `use_distortion_corrector` to false, and nothing in the profile sets it.
- *D2 held, in effect:* the Tesla rig names no `point_format`, so aib uses `xyzirc`
  (`isaac/sensors.py`, `Lidar.__init__`): no per-point times (`point_times` needs `xyzircaedt`)
  and no simulated distortion (`motion_distortion` follows `point_times`). Each cloud is one
  RTX render from one pose of the lidar prim (set to the mount's pose at the end of each substep,
  `before_substep`), every point at the header's one stamp: the stamp of the frame it was
  rendered in, `latency_frames` (2) frames back (`publish`, `_msg`).
- *So nothing is distorted and nothing is corrected:* (2) gives no across error on the straights
  at any speed. A wrong stamp would show as an along error of v times the lag (the runs' along
  errors under 0.11 m bound it to about 10 ms at 11 m/s), and in a hairpin of radius R as an
  across error of about (v lag)^2 / 2R: under 0.3 mm at 0.1 m and R 20 m. Neither the straights'
  -0.08 m nor the hairpins' +0.13 m.
- *The NTU card's limitation* ("lidar motion distortion not yet compensated in the Isaac sensor
  kit") describes the same switch: off. On the Tesla it costs nothing, because aib renders no
  distortion for it to undo; a rig that sets `xyzircaedt` (per-point times and simulated
  distortion) without the corrector on would be distorted, which the 18 runs were not.
- *What the scan side leaves:* not the mount, not the timing. Still unchecked: the render itself
  (where RTX puts a return relative to the prim, at the 1 to 5 cm level, which 169's probe
  bounded only at 0.06 m lateral at 40 m), and how NDT's voxel fit weighs a flat road's few
  lateral features. R1 to R3 on the straight fixture separate those: a level across error there,
  both ways, belongs to the render or to NDT on a flat road; none means the bends and the crown.

**G6, heading on a featureless straight (2026-11-27, before R1; from 241's run A analysis).**
In 118's run A (fixture_c6b, Isaac, the Tesla, main 7716891b) the EKF's yaw less the truth's was
-0.0114 rad (median) while driving and -0.027 rad while stopped, and over the last 6 s before the
stop the real car walked left across the lane (truth y 1.280 to 2.034 at 4.17 m/s) while the EKF
held about the lane centre: across error +0.23 to -0.39 m. A heading error δ under a controller
that tracks the EKF's lane centre walks the car sideways at v sin δ: 4.17 x 0.027 = 0.11 m/s,
about 0.68 m in 6 s against the truth's 0.75 m. On Haruna's 18 runs the yaw error was -0.007 to
+0.089 deg (step 1): two orders smaller.
- *G6 (the flat straight is not the cause):* on fixture_c170 (no props, no rocks) the EKF's and
  NDT's yaw less the truth's have medians under 0.1 deg (1.7e-3 rad) while driving, and the truth
  stays within 0.2 m of its lane's centre over the drive.
- *The alternative (run A's mechanism, the straight's lack of features):* a yaw error of the
  order of 0.01 to 0.03 rad and a sideways walk of the truth of v sin δ, growing with distance,
  in R1, R2 and R3 alike.
`err170.py` reports dyaw per topic; the truth's lateral position comes from the gap trace.
