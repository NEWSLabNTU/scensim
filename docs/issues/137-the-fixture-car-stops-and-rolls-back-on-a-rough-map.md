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
