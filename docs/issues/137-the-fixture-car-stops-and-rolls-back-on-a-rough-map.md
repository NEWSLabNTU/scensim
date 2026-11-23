# 137: the fixture car stops and rolls back on a rough map

**Status:** open, being diagnosed. **Severity:** medium until understood: a car that cannot
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
