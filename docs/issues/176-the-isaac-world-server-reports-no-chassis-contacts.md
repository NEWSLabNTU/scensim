# 176: the Isaac world server reports no chassis contacts

**Status:** closed, answered by step 1 (241, 2026-11-26): the chassis contact report exists,
as the bridge's per-run `contacts/` (the ego's cube and skid plate as one reporter). The defect
it found is issue 192. **Severity:** to be shown. No
judged check rests on a contact today. **Found:** 2026-11-25, scensim 118, while writing 086
C6e3's details (numbered by 133).

## What happens

086 C6e3's spec, as 133 amended it, records each rock's contact with the chassis (the skid
plate's and the body's) "in the world server's log". The world server logs none.
`scensim_isaac_world` has no contact report for the ego's chassis, and aib logs none either
(read 2026-11-25 at scensim main 0291abb3). C6b's plate strikes came from
`scensim_isaac_world.course.fixture_drive`, a scripted drive with its own contact report, which
a scenario run (`scensim run`, the world server) does not use.

## For C6e3 (133's decision, before any run)

No code before C6e3. A rock's contact is inferred from the truth trace: where it passed (between
the wheels or under one, from the trace and the rock's place) and the body's height and pitch at
the rock against the 10 m before it. Every row and the verdict say "inferred, not measured", and
no judged check rests on one. A rock between the wheels taller than the clearance is recorded
as "a strike likely, not measured".

## The fix (to plan)

A contact report in the world server for the ego's chassis prims (the skid plate and the body),
logged per contact with the time, the other prim and the impulse, and a run attachment that
counts them. Plan first, written before any code, after C6e3.

## Step 1: what the bridge's contact reports already see on Isaac (241, 2026-11-26; a plan, before any reading)

Approved by 133 as offline and CPU-only work, after 086 C6e3 (run 2026-11-25, 118). Nothing is changed and nothing
is run on a GPU.

**Why now.** Since issue 189 step 3 (scensim main 4dacfd6f), every scensim run is judged on the
bridge's contact reports (`<run dir>/contacts/`). The static world fails a run above 10 N*s,
and an actor fails it at any impulse. On Isaac the judge can only fail what those reports see. This
issue says the world server logs no chassis contact. But 189's survey found the reports on
Isaac already list the ego's contacts with static prims, with impulse:
- `/World/RoadRocks/r128`, 1.1 N*s, isaac_rough_road;
- the soil cut strips (`/World/soil/*_road/cut/m0`), 0.0 N*s, in 20 runs.

So some contact reaches them, and this issue's premise may be stale.

**The three questions.**
1. Which ego prims produce the reports: the chassis body, a skid plate, the wheels, or
   something else? And which prims are on the other side?
2. Does an under-body rock strike reach `contacts/`? C6e3's b1 and b2 struck the 15 cm static
   rock with the plate (b1 stopped dead from 4.17 m/s), and b2 struck the 35 cm boulder.
3. Why do the soil strips report 0.0?

**What is read, in this order.**
- *The code* (questions 1 and 3), at main 5fc2356b and its pins:
  - where the Isaac side builds a contact report (`scensim_isaac_world`, aib): which prims
    subscribe to PhysX contact reports, what "static" and the impulse are taken from, and how a
    report reaches the bridge's `contact_report_dir` (roadmap 021's remote path);
  - the ego's collision shapes in the generated rig (aib, sim_vehicle_spec's articulation and
    vehicle outputs): body, plate, wheels (raycast or sweep);
  - the soil strips' prims: collider type, kinematic or not, contact offset, and the soil
    model's own forces.
- *The kept runs* (questions 1 to 3):
  - 241's 72 Isaac reports (189's table);
  - C6e3's four runs (a1, a2, b1, b2). They are on 118's host, so I ask 118 for a copy of each
    run's `contacts/`, `result.json`, `resolved.yaml` and `junit.xml`, and the truth trace of
    b1 and b2, on the NAS. Only if they were kept.

**Predictions, before any reading.**
1. The reports come from the ego's chassis rigid body alone (its collision shapes, including a
   plate if it is a shape of that body). The wheels are PhysX vehicle wheels (a raycast or a
   sweep, not shapes in the contact report), so no wheel-rock contact appears. The rock at
   1.1 N*s is a graze of the body.
2. b1's and b2's plate strikes on the 15 cm static rock appear in `contacts/` as static
   contacts on the rock's prim, each with an impulse above 1000 N*s. b1's stop from 4.17 m/s
   takes about 1900 kg times 4 m/s, about 7600 N*s, over a few frames. b2's boulder strike
   (0.77 m/s, then creeping) appears above 10 N*s. The 15 cm and 8 cm loose rocks, under a tyre
   in b2, give no ego contact. With 189's judge, b1 and b2 would fail as UndeclaredContact with
   the static world. Both runs already failed (timeout), so no verdict changes.
3. The soil strips' 0.0 is the least sure. *Hypothesis:* they are the meshes the ego's body
   rests in or slides on at the cut's edge. PhysX reports the touch (a contact pair found), but
   no impulse, because the pair's contacts are modified or the soil's push-back is applied by
   the soil model's own forces rather than by the contact solver. The 0.0 is then a fact of the
   soil model, not a lost measurement. *The alternative:* the strips are triggers or kinematic,
   and their impulse is never computed.
4. Whatever the answers, the fix this issue planned ("a contact report in the world server for
   the chassis prims") may shrink to reading the bridge's existing reports: a run attachment
   or a measure over `contacts/`, with no new world-server code. This holds unless question 2
   finds the strike missing.

**What step 1 produces.** A section in this issue with the answers, each with its file and line or
its run. It ends with a plan for step 2: either the reader, or the world-server change if
the reports turn out blind under the body. That plan goes to 133 before any code.

### Step 1's answers (241, 2026-11-26; read at scensim main 5fc2356b, siw a736c0b, aib bb2283f)

**Question 1: which ego prims report.** The ego's whole rigid body.
- `world.py` applies `PhysxContactReportAPI` (threshold 0) to the ego's root prim, the vehicle's
  rigid body.
- `_collect_contacts` keys each contact by actor, not by shape, and sums the contact points'
  impulses per frame.
- The body's colliders are aib's chassis cube and, when the rig has one, its skid plate
  (`aib/isaac/vehicle.py`, `{path}/skid_plate`, 4 cm thick, at the rig's ground clearance).
  Both report, and the report cannot tell them apart.
- The wheels are PhysX vehicle suspension line queries (`wheel_query`: raycast or sweep). They
  are not shapes and report nothing.
- Excluded as ground (`_is_ground`): the world's `ground_paths`, the flat plane, and the road
  detail's collision tiles (`/World/RoadCollision`: cleats, potholes, the detail surface;
  issue 033's rule). Rocks (`/World/RoadRocks/...`) stay contacts.

So the prediction **held**, with two qualifications:
- the body's two shapes are one reporter;
- a strike on the road detail's own geometry (a cleat face, a pothole's rim) is ground by
  design and is never reported.

**Question 2: does an under-body strike reach `contacts/`?** Yes. From C6e3's runs (118's copy,
`~/nas/home/2026-11-26 C6e3 contacts for 176 (118)/`):

| run | contact (static) | first frame | count | max impulse |
|---|---|---|---|---|
| a1, a2 (fixture_c6a: cleats, pothole, washboard) | none | | | |
| b1 | `/World/RoadRocks/s_6_0_1578` (the 15 cm static rock, x 100) | 545 | 11549 | 8465.1 N*s |
| b2 | `/World/RoadRocks/s_6_0_1578` | 546 | 11 | 1960.9 N*s |
| b2 | `/World/RoadRocks/s_25_0_1648` (the 35 cm boulder, x 400) | 2034 | 10061 | 1536.7 N*s |

The prediction **held**:
- the plate strikes on the static rock are above 1000 N*s in both runs;
- the boulder strike is above 10;
- the 15 cm and 8 cm loose rocks, under a tyre in b2, gave none.

b1's 11549 frames are its stop on the rock and its creep. b2's 10061 are its 500 s of creeping
into the boulder (issue 182). Under 189's judge both runs fail as UndeclaredContact with the
static world. They had already failed on timeout, so no verdict changes. a1 and a2 have none: the
cleats and the pothole are the detail's collision tiles, which are ground.

**Question 3: why the soil strips report 0.0.** My hypothesis **failed**, and so did its
alternative. The strips are not soil.
- `/World/soil/<zone>/cut/m0` is `soil_tiles.cut_stage`'s copy of the *town's own road mesh*,
  with the soil zone's box cut out of it. PhysX does not re-cook an edited mesh, so the cut
  collision is a new invisible mesh under `copy_root` (`/World/soil/<zone>/cut`), and the
  original's collision is turned off.
- That copy is not in `self.ground` (the world's `ground_paths`, the plane and
  `/World/RoadCollision`), so the ego touching its own road outside the soil box is reported
  as a contact with the static world.
- Its first frame is 2 (sim 1000.1 s, the spawn) and its count about the run's length, which is
  the ego on its road from the start.
- Why the impulse is 0.0 is not settled by what was read. The wheels hold the body up, so the
  likely pair is the chassis or the plate within the contact offset of the copied mesh's faces,
  or of the kerb and verge faces it keeps beside the road: a pair with points but no solver
  impulse. Step 2 settles it by logging the pair's shape and separation.

This is a defect apart from 176: the world's own road counted as the static world. Under 189's
judge it passes only because the static floor sits above 0.0. An ego that bottoms out on that
road (a dip, a hard landing) would fail a run as UndeclaredContact with its own road. Every NPC
contact on soil in 189's table (`flat` and `cut`, 111 to 1426 N*s) is a tracked NPC resting
on the same uncounted ground. Those are not judged.

**Prediction 4 (the fix shrinks to a reader):** held for what 176 asked. The world server
already reports the chassis and plate contacts with rocks, through the bridge's per-run report.
What 176's text says was missing is a log of its own, which nothing needs.

### Step 2, proposed (for 133, before any code)

1. *A new issue for the cut road*, numbered by 133, its plan first: `soil_tiles`' cut copies
   join the world's ground, so contacts with them are not reported, as with the road they
   replace. Its test: a soil world's ego at rest reports no contact. A check: 189's 20 runs with
   `cut/m0` rerun offline show none after the fix, which needs new runs and so a GPU. The
   0.0's cause, the pair's shape and separation, is logged once while doing it.
2. *176 closes as answered* once the new issue is filed: the chassis contact report exists, as
   the bridge's `contacts/`. For C6-style rock studies, a measure reads `contacts/` per rock
   (prim path, first frame, impulse) in place of "inferred, not measured". That is 086's
   measure script, outside scensim's code.
3. *Not proposed:* telling the plate from the body. `_collect_contacts` could read the
   header's `collider0`/`collider1` and the report could carry the shape, but that changes the
   protocol's contact message, and nothing judged needs it yet.
