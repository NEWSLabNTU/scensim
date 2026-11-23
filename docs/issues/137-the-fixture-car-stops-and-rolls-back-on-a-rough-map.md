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
