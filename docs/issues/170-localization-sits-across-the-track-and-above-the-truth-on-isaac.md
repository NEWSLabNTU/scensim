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
