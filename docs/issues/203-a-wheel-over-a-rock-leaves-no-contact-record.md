# 203: a wheel that rolls over a rock leaves no contact record, so physical_verdict can pass the run

**Status:** open; plan only (241, 2026-11-28, for 133). **Severity:** medium: a judge gap. A run
can be judged physically clean while a wheel crossed a rock on the carriageway. **Found:**
2026-11-28, 241, reading issue 180's R180_D1.

## What happens

A run's contact report (`contacts/*.json`) comes from PhysX's contact reports on the car's
bodies (siw `World._collect_contacts`). A tyre does not touch the world through a contact. The
PhysX vehicle's suspension query finds the ground under each wheel, and the road layer turns that
into the tyre's force ("the egos' tire contact is the road layer's", the world server's log). So
when a wheel rolls over a rock, nothing reaches the report, and `physical_verdict`, which reads
it, has nothing to fail.

*R180_D1* (issue 180, D on r180's s 100 rock): SSv2 passed, `contacts` was empty. But as the
front axle crossed the rock, the truth's roll swung by about 1.5 deg (left side up) and z rose
about 0.035 m. The left tyre's track overlapped the rock's footprint by about 0.2 m.

R180_B1's contact (141 N s) was then most likely the body meeting the rock, after the wheel had
mounted it.

## Which earlier verdicts could have missed one (241's survey; 133 asked)

`rollover203.py` (NAS `home/2026-11-28 issue 180 step B v2 reading (241)/`) reads 41 runs'
truth traces. It flags every roll or z excursion over 0.5 deg or 0.02 m from the preceding 2 s
median while the car moves, and each excursion was checked against the placed rocks and the
contacts.
- **A clean verdict over a rock: R180_D1 only.**
- **A crossing with no contact for that rock:** b2 (issue 086 C6e3, 2026-11-25,
  fixture_c6b_down), at the loose s 200 rock: roll +0.93 deg with the front axle at x 199.9. Its
  s 100 contact had failed the run anyway.
- **Crossings the report did record:** b1, b2 and c1 at s 100; c1 at s 200 (r1602); run B's
  loose rocks; R180_B1.
- **No crossing:**
  - step B v2's 12 runs (N and D stopped 4 to 6 m short; C's contacts are recorded);
  - issue 181/182's A, A1 to A3 and B1 to B3;
  - L3's T3_6b and Y_6b;
  - the clean laps DC1 and DC2;
  - r180's step 2 run (it passed 1.2 m clear).
- **Flagged but not rocks:** fixture_c6a's designed cleats (z +0.02 to 0.035 at s 100, 200 and
  300) and pothole (roll -0.6 to -0.8 deg at s 400), and every emergency stop's dive (z 0.02,
  roll 0). So the truth's roll and z cannot judge this alone.

Nothing earlier changes verdict.

## The plan (241, 2026-11-28, before any code; for 133)

*Route 1: the wheel knows its ground.* aib already reads each wheel's ground every substep:
`Vehicle.contacts[i].shape` is the collider prim the suspension query hit (PhysX's
`VEHICLE_WHEEL_STATE_GROUND_SHAPE`), with its position and load. siw's road and surface layers
already read it. A rock's collider sits under `/World/RoadRocks`. So siw can record, beside the
body contacts, every stretch in which a wheel stands on a rock:
- `{"wheel": i, "rock": <prim>, "first_sim_time", "last_sim_time", "substeps", "max_load_n"}`,
- in the same `contacts/*.json`, as a new list `wheel_rocks` (schema 2). An older reader
  ignores it.

Route 2 (the rock placements in the record, and each wheel's track against them) is kept for
the case that step 0 below shows the query does not name the rock's prim.

*Step 0, read before code.* Whether the suspension query hits rock colliders by prim, or only
the road layer's tiles. Read the collision groups (`rock_layer.define_groups`: the wheels'
query filter against `roadDetail`), then log the wheels' ground shapes in one live run. Step 0
reads code and one run, so it has no test of its own.

*The verdict.* What `physical_verdict` does with a wheel on a rock is a policy, for 133 and the
user:
- (a) report only;
- (b) fail it as an undeclared static contact unless the scenario declares it (as body
  contacts are);
- (c) fail it only for a rock taller than some height (the car's clearance less a margin).

241 recommends (b). A scenario that means to drive over rocks (rough roads, issue 122's loose
rocks) declares it, and a scenario like fixture_c6b_r180 then fails where the car drove over
the rock.

*Tests, before code* (siw unittest, no Isaac, a fake vehicle with `contacts`):
- W1: substeps with wheel 0's shape under `/World/RoadRocks/s_6_0_1573` give one `wheel_rocks`
  entry with its first and last times, its substep count and its largest load.
- W2: the road layer's tiles and the base road (not under `/World/RoadRocks`) give none.
- W3: a wheel off the ground gives none.
- W4: two wheels over one rock give two entries; one wheel over two rocks gives two.
- W5: the JSON keeps schema 1's keys and adds `wheel_rocks` (schema 2).
- W6 (after the policy): `physical_verdict` with (b) fails an undeclared wheel_rocks entry and
  passes a declared one.

*Predictions, live* (one run each, after the code lands):
- P1: R180_D1 again (D, fixture_c6b_r180): `wheel_rocks` names the left front wheel at the s 100
  rock's prim at about the time the truth's roll swings, then the left rear about 1 s later.
- P2: fixture_c6a_down (cleats, potholes, no rocks): `wheel_rocks` empty.
- P3: a clean lap on the rock-free c6b: empty, unless a wheel leaves the lane for a shoulder
  rock, which the entry would name.
