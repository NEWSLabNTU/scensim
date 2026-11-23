# 137: the fixture car stops and rolls back on a rough map

**Status:** open, being diagnosed (the cause narrowed to the contact's or the vehicle's response). **Severity:** medium until understood: a car that cannot
hold its speed on the rough record road makes every cost or check on it a measure of something
else. **Found:** 2026-11-24, scensim 118, 086 C6d's live guard.

## What happens

`fixture_cost --follow`, one car, raycast, 10 m/s target, siw 31593ab, on C6d's *rough_rocks* and
*rough_none* maps: the car ended its run at s 265.1 and 265.0 m moving backwards (-1.18 and
-3.98 m/s). On the smooth *rocks* and *none* maps the same drive reached s 280.3 m at 9.85 m/s.

## The diagnosis (before the run)

`fixture_cost` on *rough_none* with a per-frame trace of the car (a scratch copy): s, its
lateral offset from the centreline against the lane and the carriageway's half width, speed,
the commanded speed and acceleration, the body's height and pitch, and the road's detail under
the front wheels (rut, pothole, washboard or roughness).

- **118's prediction.** The car leaves its lane, then the carriageway, near s 250 to 265 m:
  the pursuit's lateral error grows over the ruts (at +-0.80 m from the centreline, the lane's
  middle at 1.625 m, so the car's right wheels run near the left rut) or a pothole's edge. It then stops on the shoulder's foreslope or the ditch
  and rolls back down the grade, with the speed hold's command saturated. The road's height
  under the wheels shows which feature it was.

## The first findings (2026-11-24)

The *rough_rocks* probe's trace (the *rough_none* run hung, issue 139): not a stop but a launch.
At t 17.25 to 17.65 s the car's height rose from -109.1 to -100.5 m and went on to about -85 m by
18.55 s, its pitch reached 1.29 rad (74 deg), and its speed along the body swung from 8.5 to -21.9
m/s; it then came down and rolled back. It began about 0.4 s after the rear-left wheel's line
(the car at 1.97 m left of the centreline, the wheel about 0.8 m further) crossed the Poisson
pothole at u 189.10, v 2.41 (6.1 cm deep, 0.33 m radius). The prediction (leaving the lane over
the ruts) **failed**.

Offline, the record's detail and features at 1 cm along u 185 to 210 m on lines v 0.9 to 2.8 m:
no NaN and no spike, the detail between -7.6 and +1.9 cm, the pothole's edge the steepest step
(1.2 cm per cm in the detail, 2.0 in the features: its 3 cm edge), every other step under 0.1 cm
per cm. The geometry is within its spec (8 cm deep, 1 m across), so the launch is the contact's
or the vehicle's response, not the road.

## The contact probe (before the run)

`fixture_cost` on *rough_none* (a scratch copy), one car, logging per PhysX step from t 16 to
18 s only: the body's height, pitch, roll and speed, and per wheel our contact's (R5) load,
PhysX's load, the force difference applied (vertical and longitudinal), the airborne share, our
jounce and PhysX's, the effective road under it, a rim strike and PhysX's rigid limit.

- **118's prediction:** one wheel's load from our contact, the rear left's, jumps by orders of
  magnitude at the pothole's far edge, while PhysX's own stays bounded: the applied vertical
  force difference throws the body. If so, whether the edge's slope in the contact's sampling
  (its stencil spacing over the 3 cm edge) makes a near-vertical normal is checked next (133).

### The contact probe's result (2026-11-24)

*rough_none*, siw 31593ab, one car, raycast, GPU0 quiet; the trace (120 PhysX steps, t 16.0 to
17.95 s) was written at t 18.05 s, and the run then hung until its 15 min timeout (issue 139).
Wheels in aib's order: front left, front right, rear left, rear right. The launch repeats the
*rough_rocks* probe's (t 17.30 s, s 193.4 m).

- **The throw (step 1040, t 17.30 s):** under the rear-left wheel our contact's effective road
  (`w`, the envelope it makes from the road's samples) rose **1.00 m** for one step (-109.320,
  -108.315, then -109.347 m on the next) while the other wheels' moved by 2 cm. The wheel's jounce
  read 0.581 m, its rim struck (0.889), and our load was **1.60 MN** (its inner peak 2.34 MN)
  against PhysX's 25.6 kN. The body rose 0.58 m in that step and its speed fell from 8.68 to 2.83
  m/s; from there it flew.
- **Before it (t 16.45 to 17.30 s):** the front-left wheel dropped into a pothole at s 186 m
  (our load 0, then 11.7 kN at its far edge, both within a factor 2.5 of the static load). Two
  steps later (t 16.55 s, step 994) the body's speed fell by 1.40 m/s in one step (about 25 g)
  with every wheel's longitudinal force under 0.5 kN, and from step 996 three wheels were off the
  ground, in our contact and in PhysX's alike, for 0.7 s, the car on its rear-right wheel with
  its roll growing to 0.33 rad and coming back to 0.06 rad at the throw. No force we apply
  accounts for that step; what PhysX touched is not in this trace.
- **118's prediction:** the order-of-magnitude load on the rear left from our contact, PhysX's
  bounded, **held**. "At the pothole's far edge" **failed**: the load came from a one-step jump of
  our road envelope by 1 m, not from an edge's slope, and the car was already on one wheel. The
  stencil-slope question (133) does not arise: a 3 cm edge cannot make a 1 m envelope.

Two questions are open, each for a probe of its own: where the 1 m in `w` comes from (the road's
samples `h` under the rear-left wheel at steps 1038 to 1041, and the tile each came from), and
what PhysX's body touched at step 994 (the chassis's contact report, t 16.45 to 16.7 s).

## The source probe (before the run)

The same run, the code unchanged (133: 139's fix waits for 137's cause), logging two windows
only, and ended by a timeout just past them (a hang after the throw, issue 139, costs 2 minutes):

- t 17.25 to 17.36 s, every step: per wheel PhysX's hit (on the ground, its position, the
  collider) and our contact's base plane under it (the plane through PhysX's hits, refitted when
  three or more wheels are on the ground, kept otherwise); the road's samples `h` our contact
  read (each wheel's least, greatest and where), the rear-left wheel's in full; each tile the
  samples came from (its key, its bounds, its height range, made or cached) and each sample's
  grid index.
- t 16.45 to 16.70 s: the chassis's PhysX contact report (what it touched, where, the normal and
  the impulse).

- **118's prediction (a):** step 1040 is the first since t 16.6 s with three or more PhysX hits,
  so the base plane is refitted there. The rear-left wheel's hit lies about 1 m above the road
  under it, at about its suspension ray's start (an initial-overlap hit), and the refit carries
  the 1 m into that wheel's base. The tiles' detail under the rear-left wheel is smooth: within
  2 cm of the step before, from the same tile keys, every sample inside its tile. So the cause is
  not in the sample source 133 lists (a seam, a stale or wrong tile, a key collision, a default).
- **118's prediction (b):** at step 994 the chassis touches a road collider (a detail tile or the
  base road) near its front-left corner, with an impulse of about the body's mass times 1.4 m/s
  (2.6 kN s).

### The source probe's result (2026-11-24)

*rough_none*, siw 31593ab, the code unchanged, GPU0 quiet (a first start died at 7 s on a name
clash in the probe and logged nothing). The run repeats the contact probe's to the digit: the
throw at step 1040, the rear-left wheel's `w` -108.3154 m, our load 1.604 MN. It then hung (issue
139) and was stopped by its 3 min timeout after the files were written.

- **(a) The 1 m is our base plane's, not the tiles'.** Under the rear-left wheel at step 1040 the
  road's samples were -108.35 to -108.29 m (-109.36 to -109.29 at step 1039): the base plane's
  part rose by 1.00 m while the detail's stayed within 2 cm (-0.028 to -0.014 m), every sample
  from tile (5, 21), cached, 321 x 321 points, no NaN, inside the tile. The tiles are not the
  cause.

  The plane: from t 16.6 s until step 1039 fewer than three wheels had PhysX hits, so `_Car.
  _planes` kept the plane it had (z = a x + b y + c_i, b = -0.0785). Step 1039 had three hits
  (both fronts and the rear right; the rear left still off the ground), and the refit gave
  b = -0.0756 and new c_i to the three wheels on the ground, -82.896 m. The rear left, off the
  ground, kept its old c_i, -81.886 m, under the new slope. c_i is the plane's height at the
  world's origin, and the car was 349 m from it along y: the slope's change of 0.0029 moved that
  wheel's base by 0.0029 x 349 = 1.01 m. At step 1040 the rear left came down onto it (PhysX's hit
  for it then -109.299 m, where the road is), our contact read the road 1 m above its true place,
  and the next refit, with four hits, put the base back. A stale intercept carried under a new
  slope: the further from the origin, the larger the error.
- **(b) The skid plate struck a detail collision tile at step 994.** The chassis's report at
  t 16.45 to 16.70 s: the body and the skid plate in contact (within their contact offsets) with
  the base road, the terrain and tile `t_5_21_26` at every step, all with no impulse except one
  point at step 994: the skid plate on the tile at (81.60, 345.30, -108.996), its normal (-0.021,
  -0.479, 0.877) (a face 29 deg from level, facing the car: the pothole's far wall in the tile's
  5 cm mesh), separation +0.083 m, impulse (-133, -3011, 5513) N s, 6.28 kN s along the normal.
  Its component along the road, 3.0 kN s, is the 1.4 m/s the car lost in that step. The gap was
  open (+8.3 cm); the car's 10 m/s along that face's normal closes about 4.8 m/s, 8 cm in one
  1/60 s step, so the solver acted on the contact as one the step would close.
- **118's predictions:** (a) the refit there and the 1 m in the base, with smooth tiles from the
  same keys, **held**; "the rear-left wheel's hit about 1 m high, an initial overlap" **failed**:
  that wheel had no hit in the refit's step, and its base came from its stale intercept. (b) a
  road collider near the front-left corner at step 994 **held** (a detail tile, the plate's front
  left); the impulse, 2.6 kN s predicted, was 6.28 kN s (2.4 times).

Two defects, each on its own: (a) is ours, and it throws the car; (b) starts the 0.7 s on one
wheel that brings (a) about. Whether (b) is a true strike (the plate's front edge reaching the
wall's top) or PhysX acting on the face's plane beyond the 3 cm wall is not settled by this
trace.

## The fix (before the rerun)

`_Car._planes` keeps each wheel's last PhysX hit and, at a refit, puts each wheel's c_i through
its own last hit under the new slopes, the plane written about the hits' centre (x0, y0), not
the world's origin: z = a (x - x0) + b (y - y0) + c_i. A wheel never on the ground takes the
hits' mean. `test/test_issue_137.py`:

- a refit 349 m out with the rear left off the ground: its base at its last hit is that hit's
  height (to 1e-9 m). On siw 31593ab the same case is 1.013 m off.
- the same with the rear left's last hit at the origin: the same base as before.
- four wheels on the ground 350 m out: each wheel's base is the old plane's to 1e-9 m and passes
  through its hit. Not bit for bit: about the centre, the sums are taken in another order.
  133 asked for both a centred plane and a bit-identical four-hit case; the two cannot both
  hold, and 133 accepted 1e-9 m, the centred plane mattering more.
- fewer than three hits keep the plane and still record the hits; a wheel never on the ground
  takes the hits' mean.

Other places that fit or keep a plane (133's question), none carrying a world-origin intercept
across a change: `surface_layer.sink_pose` (body frame), `soil_tiles.footprint` (about the
plate's centre), the road contact's envelope (along the wheel's heading from its contact), and
`rocks.RockSet.planes` (world-frame offsets, n . X <= h, recomputed from the rock's pose
whenever it moves; at 350 m a float64 offset is exact to about 1e-13 m). aib fits no plane; it
reads PhysX's hits as they are.

- **118's prediction for the rerun** (*rough_none*, one car, the contact probe's per-step log
  from t 16 to 18 s, the code fixed): no throw. The front-left wheel's pothole at s 186 m and the
  skid plate's strike at step 994 (issue 140, not touched by the fix) are as before, to the digit
  up to step 1039, and the car again spends about 0.7 s on its rear-right wheel. When the wheels
  come down at t 17.3 s, the rear left's road under our contact (`w`) stays within 5 cm of the
  step before, and its load is within a factor of 3 of PhysX's at the same step (not 1.6 MN). The
  car drives on to the run's end (`cost.json` written, s past 250 m). If the run stops early, its
  cause is named from the log; a hang after the frames are done is issue 139's, not a throw.

### The rerun's result (2026-11-24)

*rough_none*, siw `issue-137` 4df3198, one car, raycast, GPU0 quiet: the run ended by itself
(rc 0, 25 s) with the car at s 278.8 m and 9.87 m/s. No throw, no hang.

- **No throw: held.** At the landing (step 1040) the rear left's `w` went from -109.320 to
  -109.311 m. Over t 16 to 18 s the body's height stayed between -109.75 and -108.36 m (the slope
  of the road) and no wheel struck its rim beyond 2.2 cm.
- **"As before to the digit up to step 1039": failed.** The trace first differs at step 997
  (t 16.6 s): with fewer than three wheels on the ground from step 996, the wheels off the ground
  now take their bases from their own last hits, so the fix acts from there, not only at the
  refit. The car's course is the same to a few mm and cm/s until the landing (roll at most
  0.329 rad, 0.33 before; speed 8.64 m/s at step 1038, 8.63 before), and the skid plate's step
  (issue 140) is before 997 and unchanged.
- **"The rear left's load within a factor of 3 of PhysX's at the landing": failed at the first
  step, held after.** At step 1040 our load was 1.04 kN against PhysX's 13.1 kN (12.6 times
  less: our wheel meets the road later in the step than PhysX's rigid one); from step 1041 on it
  was within a factor of 2.1 (9.3 against 18.7 kN). The largest load from our contact over t 16
  to 18 s was 49.1 kN, the front left at step 1042 with a 2.2 cm rim strike as the car settled,
  against PhysX's 27.5 kN largest; R4's peak is 57.5 kN.
- **"Drives on to the run's end": held.** `cost.json` written, s 278.8 m, past the 265 m where
  both rough maps had stopped and rolled back.
