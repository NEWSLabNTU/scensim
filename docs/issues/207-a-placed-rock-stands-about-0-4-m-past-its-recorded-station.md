# 207: a placed rock stands about 0.4 m past its recorded station

**Status:** open; recorded, owner to be found (133). **Severity:** low, but it shifts every
measure that takes a placed rock's station as its position. **Found:** 2026-11-28, 241,
replaying R180_NH1 for the low-rock remedies (issue 180).

## What is seen

fixture_c6b's road record (`road_detail.yaml`, `rocks.at`) places the 15 cm rock at
`[100.0, 2.425, 0.15, 0.1, 0]`: station u 100, offset 2.425, height 0.15 m, 10 % embedded, fixed.
The corridor's centreline has x = u (`section.npz`), so the record says x 100.0. The rock in the
world is about 0.4 m farther along:
- *The lidar.* On R180_NH1 (scensim b4c77328, the rebuilt c6b map), the lane check's obstacle
  points on the rock, placed by the EKF's pose, lie at x 100.37 to 100.68 (median 100.50),
  y 2.33 to 2.52. The EKF's along-track error against the truth was -0.020 m at that moment,
  and -0.032 m at the first stop factor, so the placement is not localization's.
- *The contact.* On R180_D1, the car's front axle was at x 100.1 when the left front tire met
  the rock (the truth's roll swing). On R180_B1 the axle was at x 100.4 at the first contact,
  as the car crept on. Both put the near face near x 100.4, not about 99.85.
- Issue 196's lidar lag (about v (n - 1) dt, 0.14 m at 4.17 m/s and 60 Hz) would place points
  that much farther. Against a near face known to about 0.1 m, it is not separable here, and
  it cannot explain 0.4 m.

Not yet known: where the 0.4 m comes from. `rocks._fixed` sets the rock's position at the
station and offset and its z from the surface. Candidates to check:
- the fixed prototype's vertices are not centred on its origin in xy;
- the layer's origin offset (`RoadLayer` `ox`, `oy`, which `RockStream._load` subtracts);
- the centreline's segment lookup (`seg_u`, `seg_dir`) for a fixture whose u starts at 0.

## Who reads a station as a position

- **241's issue 180 judges and readings**, by `--rock-x 100.0`: `judge_stepB180.py`,
  `judge_stepB180_v2.py` (v2.1), and the readings made with them.
  - *R180_B1's "stopped 0.06 m short"*: measured against a near face at about 99.82 from the
    station. Against the near face at about 100.4 the car stood about 0.6 m short.
  - *Q2's first detection distances* (R180_B1 8.0 m, R180_NH1 6.51 m to the station) are about
    0.4 m longer to the real rock.
  - Step B v2's fixture_c6b_r181 boulder (`--rock-x 399.8`, its x from siw's placement, not the
    station) is not affected.
- **siw `course/rock_check.py`, `placement`** reads `rocks.at` as the record and checks cover
  and that no placed rock lies on the carriageway. A 0.4 m shift along the road changes
  neither, so its verdicts stand.
- **The lane check, obstacle_stop and the truth's contacts** read the world, not the record:
  unaffected.

## The fix's shape (for its owner)

Find which of the candidates moves the rock, then either place the rock at its station or
record the placed pose beside the station (the run's `attachments`), and let judges read the
placed pose. Until then, a judge takes a placed rock's position from the run, not the record.
