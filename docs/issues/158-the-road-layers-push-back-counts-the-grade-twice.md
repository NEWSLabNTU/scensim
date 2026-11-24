# 158: the road layer's push back along the road counts the base road's grade a second time

**Status:** fixed: scensim_isaac_world 31adacc (scensim main a41f92c7, 2026-11-25); the
affected results' reruns and notes below. **Severity:** high on graded road-detail worlds: on any grade the car feels the grade's
pull twice, forward downhill and backward uphill, about the load times the grade (1100 N on a
6 % grade for aib's Model 3). **Found:** 2026-11-25, scensim 118, issue 157's force balance
(numbered by 133).

## What happens

R5's tire contact (`road_contact.TireContact.step`) returns per wheel `dfx`, "the effective
plane's push back along the wheel's heading": minus the tire's load times the slope of the
cams' effective road, at the contact. The road layer (`road_layer.RoadLayer`, its car's `step`)
gives the cams the true road as `base + detail`, the base being the plane it fits through the
wheels' PhysX hits (`_planes`). So the cams' slope is the plane's grade plus the detail's own
slope. PhysX already carries the plane's grade (the body pitched on it, gravity along it, its
suspension along the body's up), so the plane's part of `dfx` is a second grade force.

- On a plane of slope -0.06 the envelope's slope is -0.0589 (offline, `TireContact.envelope`).
- `test_road_layer`'s stand-in car on a bare corridor (no detail, no crown) gets `dfx` summing to
  0 N level, 1102 N against the slope at 6 % and 1801 N at 10 %, the load times the grade
  (offline, siw 30eb19a).
- On issue 157's 3.4 degree downhill that is about 1000 N forward: the force 157's probe was
  missing. With it the sand ramp's equilibrium is 2 x 0.027 = 0.054 m/s, against the 0.055
  measured.
- `test_no_detail_no_force_on_a_grade` asserts the vertical force only, so it passed.

The road layer exists only on worlds with a `road_detail.yaml` (`world.py` `_load_road` returns
without one). Worlds with surface zones only (Town01 on Isaac, the published Haruna) never build
it and are not affected.

## Reach (written before the fix, 133)

Every result on a road-detail world with grade. "Judged deltas" are A/B results whose two sides
both ran the road layer on the same road: the second grade force is in both, so the difference
stands to first order, though the car's own speed and braking do not. "Absolutes" are numbers
judged or reported against a fixed bar or a reference.

| result | road detail, grade | what can move |
|---|---|---|
| 086 C4's Haruna runs (056 acceptance items 1 and 2, testbench `isaac_c4_haruna`) | C6b's Haruna record course, its descent | the judged items (the named map set at Init, a refusal reaching SSv2) do not depend on the car's speed; scenario 1's crawl on sand, and its trigger changed from 20 m to 30 s of sim time, came from 157, whose speed this halves (the ramp alone still creeps) |
| 086 C5b, C5d, C5d2 (fixture courses `fixture_c5`, `fixture_c5d2`) | -3 % along the whole course, but no road layer in the world server: the course's road detail is in `course/`, not the map directory | unaffected. *Corrected after the C5d2 rerun (below): written first as "can move"; the world server never loaded a road detail on these maps, so their Autoware runs never had the force* |
| 086 C5's exit pairing (haruna_down, published Haruna) | none (no `road_detail.yaml`) | unaffected; issue 116's closure stands |
| 086 C5c (`fixture_c5c`), C6a, C6b's fixtures, C6c | level | unaffected |
| 086 C6b's budget on Haruna (rocks against none) | Haruna record course | judged deltas (frame p50 and p95, rocks against none, both with the road layer) stand; the driving under them (speeds, braking) does not |
| 086 C6d (sensors and Autoware, rocks against none, three runs a side) | Haruna rough | the judged delta (+0.0003 m mean pose error p95) stands; the absolutes reported beside it (pose error, NVTL, false stops a km, NDT iterations) can move |
| issue 142 (rocks' and tiles' leads on Haruna at 8.3 to 20 m/s) | Haruna record course | the leads were measured at speeds a speed hold kept, so they move only through the hold's tracking; the stopping distances they were judged against were computed from the speed, not driven: unaffected |
| issues 128, 134, 144, 147, 152 (tile and rock timing and placement on Haruna) | Haruna record course | wall-clock and placement measures at held or Autoware speeds: absolutes only through the car's speed; none judged a dynamic quantity |
| issue 157 (sand crawl) | Haruna, `haruna_sand` | its speed, by half (above) |
| 066 R3's rough road and its 80 km/h run, R5's 055 suite (`spikes/proving_ground_road`), R4 and R5's fixtures, the Town01 example | level or the proving ground's flat road | unaffected to first order (no grade) |
| 094 P4 (Town01 on Isaac, 139's and 241's training) | none: `scensim_batch`'s tasks run on a flat lanelet plane with no road layer | unaffected |
| aib's slope matrix, 055's manoeuvre suite | none (a ground plane, gravity tilted) | unaffected |

## The fix (planned; 133 approved F1 to start, test first)

- **F1.** `dfx` from the cams' slope less the base plane's slope along the same heading, so a
  plane gives no push and only the detail's slope does.
- **The test, written first, failing on today's code:** the bare corridor at 0, 6 and 10 %
  gives `dfx` within 1 N of 0 on every wheel; a crest and a sag (a corridor whose base rises and
  falls on a vertical curve of 100 m radius) the same; a water bar's push unchanged on a level
  road and within 1 % of it on a 6 % grade.
- **118's prediction for the crest and sag, before running:** within 1 N, by construction. The
  layer's base under the wheels is the plane fitted through their hits each step, not the
  curve, so the cams read plane + detail and subtracting the plane's slope leaves the detail's
  only. (The base's own curvature under one footprint, about 0.11 m at 100 m radius, is not in
  the layer's model at all; that is the plane fit's approximation, not 158's.) Today's code
  fails each case by the load times the plane's slope, 260 to 475 N a wheel on the grades.
- Then issue 157's P2 probe, and the results above rerun or annotated, named for 133.

## F1, written and tested offline (2026-11-25; siw local branch `issue-158`, 31adacc, not pushed)

- **The fix.** `TireContact.step` takes out the base's slope as the cams read it
  (`TireContact.base_slope`: the base's height at the first and last cams' stations, rounded to
  the DU grid as `envelope` rounds them, over the cams' spacing), then gives `dfx` from the rest.
  A first form, the base's slope from two points 5 cm either side of the contact, left 4.7 to
  5.3 N a wheel on 6 %: the cams' stations are rounded to 1 cm, so their slope reads a plane
  about 2 % under its grade (-0.0589 on -0.06). Taking the base at the cams' own stations
  cancels a plane exactly. On a level road the base's slope is 0 and `dfx` is unchanged bit
  for bit, so the level fixture checks (C6a, C6b, C6c) cannot move.
- **The tests.** On today's code the bare corridor failed, 260 to 291 N a wheel on 6 % (118's
  prediction: the load times the grade, held). With F1:
  - the bare corridor at 0, 6, 10 and -6 %, and on a 100 m crest and sag at 0 and 6 %: under
    1 N a wheel. The crest and sag prediction (within 1 N, by construction) held;
  - *the water bar, amended after the offline test result, before any Isaac run* (the reason:
    the geometry, r sin(grade)): the test as planned (the bar's push over the
    load at the same hub place, level against 6 %, within 1 %) cannot hold, and not because of
    158: a disc on a grade meets the road r sin(grade) uphill of below its hub (2.2 cm here), so
    at the same hub place the two read different points of the bar's flank (0.129 against
    0.076 at 9.95 m). The test now compares the flank's largest slope (within 1 %, held) and its
    place, shifted by r sin(grade) (within 1 cm, held).
  - the rest of siw's suite as before F1 (the same environment's errors, none new).
- **Next:** issue 157's P2 probe on F1 (Isaac, GPU0, non-timing), then the landing with its
  results, after 133's word.

## Issue 157's P2 on F1 (2026-11-25, 04:48 to 04:51, 118)

The free arm (no ECU, no torque) on `p157_sand`, siw probe158 4ca9246 (F1, 31adacc, with 157's
probe extended to log the forces along the road; local, never landed) in gate-c5c for the run,
restored to 30eb19a after; GPU0 empty at the start, non-timing (codec told); the scenario passed;
962 records, 862 after the first 10 s. After the first 10 s (medians, 5th to 95th percentile):

| quantity | P2 (F1) | 157's free arm (before F1) |
|---|---|---|
| speed, m/s | 0.0253 (0.0241 to 0.0261) | 0.0515 to 0.0557 |
| gravity along the road, m g sin(pitch), N (m 1840 kg, pitch 3.29 deg) | 1036 (997 to 1063) | |
| soil, as applied (-resistance x share x ramp), sum, N | -951 (-975 to -910) | |
| road layer `dfx`, sum, N | 0.0 (every record under 0.05 a wheel) | about +1000 (158) |
| m a - gravity - soil - dfx, N | -85 (-96 to -74) | |
| PhysX's `WheelState.force[0]`, sum, N | -3867 (-3880 to -3837) | not logged |

- **The creep halves**, from 0.052 to 0.055 m/s to 0.024 to 0.026: the ramp alone (its
  equilibrium from one record's numbers, 0.1 x 991 / 3761 = 0.026 m/s). 158 was the other half.
- **The forces along the road close without the tyres**: gravity, the soil and `dfx` leave
  -85 N, 8 % of the pull, with the body's acceleration near 0.
- **118's predictions:** `dfx` under 50 N held (0); the residual under 100 N held, taken
  without the tyre field (-85 N); the creep at 0.026 to 0.028 m/s **failed**, just under it
  (0.0241 to 0.0261); the tyres under 20 N **failed as measured**: aib's `WheelState.force[0]`
  reads -930 to -1020 N a wheel, about 0.22 of each wheel's load, steady. As a force on the car
  along the road it would decelerate it at 2.1 m/s^2 against a measured 0.00, so it is not one
  here; what PhysX reports in that field at this speed (below its sticky-tyre threshold, 0.2
  m/s) is not settled by this run, and nothing here uses it.
- So 157's creep is now the ramp's alone, F2's question; 158 is fixed by F1 for the creep.

Record: NAS "2026-11-25 issue 158 F1 and 157 P2 (118)".

## Rerun or annotate (133's decision, 2026-11-25), and the predictions, before the runs

- **Annotated, not rerun:** C6b's Haruna budget and C4's Haruna runs (a note at each in 086),
  and issues 128, 134, 142, 144, 147 and 152 (this issue's reach table stands as their note):
  none judged a dynamic quantity that the force moves.
- **C5d2: rerun once** on main a41f92c7, its bars unchanged (NVTL p05 at least 2.5, pose error
  p95 at most 0.2 m, the scenario passing); a fresh testbench workspace built against that
  install, `isaac_c5d2_fixture`, `fixture_c5d2_down`, GPU0 non-timing. Before: passed, 127.4 s,
  NVTL p05 3.08, pose error p95 0.103 m (median 0.054, max 0.127).
  118's prediction: passes; pose error p95 0.07 to 0.14 m; NVTL p05 3.0 to 3.15; the run's
  simulated time within 5 % of 127.4 s. On -3 % the second force was about 0.03 of the load
  forward, which Autoware's speed control took out with less drive or more brake; with it gone
  the speed profile, which the planner sets, should stay, and with it the scan's poses.
- **C6d: one run a side** (rough_rocks r4, rough_none n4) on a41f92c7 under C6d's runner and its
  quiet rule, each side's testbench rebuilt against that install; the absolutes then annotated
  with the measured shift. Before (means of three): pose error p95 0.1238 m rocks, 0.1235 none;
  NVTL p05 3.118 and 3.119; false stops 0 a km; NDT iterations p50 / p95 3 / 4.
  118's prediction: both pass; each pose error p95 within 0.02 m of its side's earlier mean,
  unless the run falls in Haruna's high mode (about 0.18 m, C5's exit pairing), which is then
  named as that mode, not a shift; NVTL p05 within 0.02 of 3.12; false stops 0; NDT iterations
  3 / 4. The rocks' delta is not judged again from one run a side.

## The reruns' results (2026-11-25, 05:13 to 05:31, 118, GPU0)

Scensim main a41f92c7 (gate-c5c's install; every run's live bridge under it, `result.json`
naming 4998daa1+dirty, the gate commit whose tree is a41f92c7's, the dirt `Cargo.lock` files
only, as C6d's runner accepts); GPU0 with nothing else on it; codec told. NAS "2026-11-25 issue
158 reruns (118)".

- **C5d2** (2026-11-25T05-29-03): passed, 127.436 s (127.4 before), NVTL p05 3.079 (3.08),
  pose error p95 0.106 m (0.103), median 0.054, max 0.121. **Every prediction held.** But the
  reason is not the one written: the run's log has no road detail line, and `fixture_c5d2` has
  no `road_detail.yaml` in its map directory (the course builder writes it to `course/`), so the
  force never reached C5d2's Autoware runs. The reach table is corrected (labelled). A first
  attempt at 05:13 was refused by scensim's check before it drove (the map not fetched into the
  testbench's package); fetched and rebuilt, it ran at 05:29.
- **C6d one a side** (the runner's quiet rule passed at the start of each):

  | run | pose error p95, m | NVTL p05 | false stops a km | NDT iterations p50 / p95 | simulated, s |
  |---|---|---|---|---|---|
  | r4 rough_rocks (2026-11-25T05-13-55) | 0.1243 (before: 0.1238 mean of three) | 3.118 (3.118) | 0 (0) | 3 / 4 (3 / 4) | 424.5 (413.5 to 457.7) |
  | n4 rough_none (2026-11-25T05-21-37) | 0.1230 (0.1235) | 3.118 (3.119) | 0 (0) | 3 / 4 (2-3 / 4) | 408.5 (397.5 to 427.8) |

  The road layer ran in both (the log's road detail line). **Every prediction held**: both
  passed, each pose error p95 within 0.0005 m of its side's earlier mean (low mode), NVTL p05
  within 0.001 of 3.12, no false stops, NDT 3 / 4, durations inside the earlier runs' spread.
  So on Haruna the second force moved none of C6d's absolutes measurably: Autoware's speed
  control took it out (it braked against it), and the trajectory and the scans did not change.
  C6d's absolutes stand as recorded, now with this note.
