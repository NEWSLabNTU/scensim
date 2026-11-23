# 086: Track C: Road and Terrain Physics

One tyre-and-ground model: surfaces and soil (wet, gravel, mud, sand, snow), calibration against measurements, the scenario choosing its ground, small obstacles and roughness, and the road section itself (bank, crown, edges).

**Status**: consolidated 2026-11-18 from 047, 052, 053, 056, 066, 069. Owner swb 118 from
2026-11-20 (user, through 133). 2026-11-20: re-planned as one model ("The plan" below),
approved by 133 the same day with its three decisions. C1 done 2026-11-20 (scensim_isaac_world
87e0ea1, pins f00f02a2). C2 done 2026-11-20 (scensim_world_protocol 2519aca, scensim_isaac_world
51a95b4, pins 7aad5216). C3 done 2026-11-20 (scensim_isaac_world 98a5d8c, pins 4c67e51d); the
courses' dataset revision prepared, not published. C4 landed 2026-11-20 (scensim_isaac_world
6177ced, scensim 82787b91); its Town01 suite waits for 139. C5 started 2026-11-23 in four
steps ("C5's steps" below); C5a done (scensim_isaac_world ea35f35), C5b done
(scensim_isaac_world b5de87b, its fixture course and checks), C5c done (scensim_isaac_world
7eb96cc, the lip fixtures and the strips as zones), C5d done with one failed check
(scensim_isaac_world 33c6aae: the maps pass, the fixture's localization fails), C5d2 done
(scensim_isaac_world 41a0102: the fixture with guardrails and trees passes). C5's exit
pairing done (2026-11-23): the slope matrix and haruna_down unchanged by C5; C5 closed
2026-11-23 (133's review).
Issue 077's cause is confirmed (2026-11-20, 118): PhysX's raycast wheel query takes Town01's
sharp curb face as the ground, and Town01 has no road layer. Its fix comes first, ahead of C5:
recheck the sweep (066 R1's check, from C6). If the sweep no longer throws the car, aib switches
to it. Otherwise the curb becomes C5's lip on a Town01 road record.

**Research rule** (user, 2026-11-18): a research track does not wait for scensim releases.
Its work runs on current scensim main, and it moves to each new scensim release when that
release is published (rebuild, rerun the track's reference runs), as a deliberate step.

**Consolidated** 2026-11-18 (user: "Have A-D"): the phases below keep their own documents as
history and detail; this document is the track's plan and status from now on, and new work
is planned here.

## Parts

| phase | what | status | left |
|---|---|---|---|
| [047](047-off-road-surfaces.md) | off-road surfaces | done 2026-10-23 (every step and acceptance item) | nothing; its open ends moved to 052 and 053 |
| [052](052-isaac-physics-completeness.md) | Isaac physics, feature-complete | in progress: steps 1-5 done (physics egos) | the lead NPC's sinking seen by camera and lidar; Autoware egos with 039 |
| [053](053-terramechanics-calibration.md) | soil calibration against published measurements | in progress: sand, mud and snow fitted | dirt (no data); dropping the flags; the field (040) |
| [056](056-scenario-surface-maps.md) | the scenario chooses its ground | planned | named surface maps, label classes |
| [066](066-small-scale-road-physics.md) | small-scale road physics: rocks, roughness | in progress: R0, R2, R3, R5 done; R4 three slices | R1 checks, R4, R6 wheel hop, R7 sensors, R8 the section |
| [069](069-road-tilt-load-and-edges.md) | road tilt, tyre load and the road's edge | planned, design only | the road-section record (E0, this track's C3); E1, E2, E4: Track B, unassigned |

## Folded in

- Isaac only today; CARLA 1.0's Chaos vehicle ([083](083-carla-1-0.md) step 5) is a second target for the surface classes.

## The plan (re-planned 2026-11-20)

### What there is today

Three files describe the ground to the simulator, written by different hands and read
separately:

| file | phase | holds | written by | read by |
|---|---|---|---|---|
| `<map>/surfaces.yaml` | 047 | a class per ground label (`defaults`), zones (polygons, class, wetness, water depth, soil) | hand; the course builder (labels only) | the Isaac world server's surface layer; nothing on CARLA |
| `scensim_isaac_world/config/surface_classes.yaml` | 047, 053, 054 | per class: friction, wet factors, the tyre curve's shape, hydroplaning, soil (Bekker-Wong-Janosi), its calibration source | hand; 053's fits | the Isaac surface layer and soil |
| `<map>/road_detail.yaml` | 066 R3 | corridors: a centreline, a seed, roughness class, one constant `section` (half width, crown, shoulder), ruts, potholes, washboard, water bars, rocks | hand | the Isaac road layer (contact, render tiles, rocks) |
| `course/section.npz` | 069 E0 | per 1 m station: bank, crown, vertical curvature, per side shoulder, lip, foreslope, ditch, run-off, barrier, hazard class | nobody yet (planned) | planned: Isaac's ribbon, `road_detail`, the rails, autoware-drift's `Track` and plant |

Two of them already overlap: `road_detail.yaml`'s constant `section` and 069's per-station
section are the same thing at two resolutions, and 069's `shoulder_surface` and
`runoff_surface` are surface classes that `surfaces.yaml` would otherwise hold as zones. And
the course builder computes the ground's drop for the guardrails (`course/props.py`) and
throws it away.

### What 070 and 072 taught

- **070 (the Isaac ego did not start downhill).** PhysX's sticky-tyre hold leaves only on drive
  torque, so a brake request below the floor held the car on a 3.1 deg slope. The ground's
  grade decides whether a car moves at all at low speed, and the fault sat between the
  car's computers and PhysX, not in the ground. So: a step that touches the tyre contact
  (066 R5, R6, R8) reruns aib's slope matrix (`aib.steptest`: start and hold on a downhill,
  flat and uphill) as part of its exit check, and the car's side (aib, sim_vehicle_ecu) stays
  a consumer of the ground record, never a writer.
- **072 (Haruna's point cloud was too large for the compare-map filter).** A map's files are
  read by consumers we do not own, and their limits (an int32 voxel count) set the format. The
  error showed up 230 m down the course as an obstacle stop, far from its cause. So: every
  record is checked when it is loaded, by the code that reads it, naming the fix; a road
  change that moves the ground (bank, crown, lip) regenerates Autoware's maps (point cloud,
  lanelet heights) from the same meshes, in the layout the profile expects (divided above a
  size); and a record change in a published map is a dataset revision with a new tag (scensim
  resolves the newest tag), which the user publishes.

### Shared data and consumers

**Shared data: two records, both in the map directory, both simulator-neutral.**

1. **The surface record**: `surfaces.yaml` as it is (label defaults, zones), plus the class
   table it names. The class table moves out of the Isaac world server into
   `scensim_world_protocol` (installed share, versioned with the protocol), so that the CARLA
   world server and the road record read the same class names and values without depending on
   Isaac's package. Classes keep every field they have; a simulator uses what it can (CARLA:
   `mu`, `wet`; Isaac: all of it).
2. **The road record**: `<map>/road_detail.yaml`, a list of corridors, each with a centreline,
   a seed and its section **per station**, which takes the place of 069's planned
   `course/section.npz` (C1 kept the file's name: the `isaac-road-physics-stages` dataset and
   scensim's testbench key `ground.<map>.road_detail` already carry it, and renaming it would
   need a dataset revision for nothing):
   - per corridor in YAML: `centreline` (or `stations: <corridor>.npz`), `seed`, `roughness`,
     `ruts`, `potholes`, `washboard`, `water_bars`, `rocks` (066 R3/R4's keys, unchanged);
   - the section: either constants in YAML (today's `section:`, expanded to every station) or
     arrays in `<corridor>.npz` over the corridor's stations: 069's fields with 066 R3's
     (`half_width`, `bank`, `crown_offset`, `kappa_v`, and per side `crown`, `shoulder`,
     `foreslope`, `ditch_depth`, `ditch_bottom`, `backslope`, `lip_h`, `lip_angle`,
     `runoff_len`, `barrier_offset`, `shoulder_surface`, `runoff_surface`, `hazard`; in the
     .npz `<field>_left` and `<field>_right`);
   - surfaces in the section are class names of the surface record's table; the shoulder and
     run-off strips become zones of the surface layer, generated from the record at load, not
     written twice;
   - `schema: 1` at the top; a reader refuses a newer schema by name.

**Who writes them.** Never the simulator at run time.

| writer | writes | when |
|---|---|---|
| the course builder (`scensim_isaac_world.course`) | `road_detail.yaml` and the `.npz` for a generated course (Haruna, Tsukuba): sections from its own geometry, `kappa_v` from the smoothed profile, the hazard classes from one classifier (today's rail rule, kept) | at build; shipped in the course's dataset |
| a map author | `road_detail.yaml` with constant sections for a town corridor, `surfaces.yaml` zones | by hand, checked by `road_detail check` and `surfaces check` |
| 053's fits | the class table's soil rows and their `calibration:` | per fit |
| later, a twin fitter (087) | sections fitted to a scan with a curvature penalty (069's note on noisy sections) | per twin |

**Who reads them (the consumers).**

| consumer | reads | phase |
|---|---|---|
| Isaac surface layer | surface record; the record's shoulder and run-off strips as zones | 047 (done), extended |
| Isaac road layer: contact, render tiles, rocks | road record (per-station section, detail keys) | 066 R3-R7 |
| Isaac course geometry: ribbon, rails, Autoware maps | road record (bank, crown, lip, barrier) | 066 R8 |
| the scenario | names a surface map, sets label classes (`swb.surface_map`, `swb.default.<Label>`) over the surface record | 056 |
| CARLA world server (0.9.16 and 1.0 Chaos) | surface record: zones as friction trigger boxes, `mu` and `wet` | new, step C7 |
| autoware-drift's planner and plant (Track B, 085) | road record (`Track.from_swb_course`) | 069 E1, E2, E4 (Track B, unassigned) |
| aib, sim_vehicle_ecu | nothing directly; they feel the ground through PhysX and the contact forces | 070's slope matrix as a check |

So of 047/056/069: **047's `surfaces.yaml` and class table, and 069's section, are the shared
data**; 056, 066's layers, CARLA and the planner are consumers. 069 splits: E0's record is
this track's, E1, E2 and E4 (the planner's equations and edge pricing) are Track B's work in
autoware-drift, reading the record: Track B, unassigned (085 has no active owner).

### Steps

Each step on current scensim main; the exit check is what lets the next step start.

| step | what | effort | exit check |
|---|---|---|---|
| **C1. The road record and its reader** (done 2026-11-20) | `road_detail.yaml` schema 1; a pure reader and checker in `scensim_isaac_world` (`road_record`, every problem named, `road_detail check <map>`); constant sections and per-station `.npz` both become stations | 1 week (took 1 day) | every converted example builds the same detail tiles, byte for byte (tile hashes before and after); `test_road_detail`, `test_road_layer` pass; a malformed record lists every problem |
| **C2. The class table moves to the protocol package** (done 2026-11-20) | `surface_classes.yaml` into `scensim_world_protocol`'s share; both world servers find it there; the road record's surface names checked against it | 3 days (took half a day) | Isaac: the Town01 soil, mud and snow scenarios pass as on 053 step 5; an unknown class in a section or zone is refused at load |
| **C3. The course builder writes the record** (069 E0, swb half; done 2026-11-20) | `road_detail.yaml` + `<corridor>.npz` from the builder: bank 0, today's section, `kappa_v` from z, the hazard classifier from today's rail rule; `props.py` places rails from `barrier_offset` | 1 week | Haruna and Tsukuba rebuilt: the same rails at the same positions, the world USD unchanged except the new files, `haruna_down` still passes; the course's dataset revision prepared, published only on the user's go |
| **C4. Named surface maps** (056; landed 2026-11-20, Town01 runs pending) | as 056's steps 1-5 | 1-1.5 weeks | 056's acceptance: Town01's soil scenarios one after another on one world server, no file copied |
| **C5. Isaac's geometry from the record** (066 R8) | the ribbon tilted by bank and crown; `road_detail` per station; the lip; the shoulder and run-off strips as surface zones; Autoware's point cloud and lanelet heights regenerated from the same meshes, divided when large | 1.5-2 weeks | Isaac's road height and cross slope within 5 mm and 0.1 deg of the record at every station; lip re-entry fixtures (5, 10, 15 cm at 90, 45, 30 deg); aib's slope matrix unchanged; `haruna_down` passes on a course with a nonzero crown |
| **C6. The rest of 066** | R1's checks, R4 rocks finished, R6 wheel hop, R7 sensors and Autoware, all reading the road record | 5-7 weeks, in 066's order | 066's acceptance; aib's slope matrix and 055's manoeuvre suite unchanged on smooth road |
| **C7. CARLA as a second target for the surface record** | the CARLA world server reads `surfaces.yaml`'s zones as friction trigger boxes (class `mu` x `wet`) and takes `swb.zone.<id>.*`; on 0.9.16 first, then on CARLA 1.0 once 083 step 5 maps the spec to Chaos; label defaults stay asphalt (CARLA's towns have no ground labels per wheel) | 1 week (0.9.16), 3-5 days more (1.0) | a wet zone and a split-mu zone change the CARLA ego's stopping distance and yaw the same way as on Isaac, within 25 % of Isaac's for the same class, on both CARLA versions; the T3 suites unchanged without zones |
| **C8. Calibration and the open 052 item** (independent) | 053: dirt when data comes, step 4 (dropping the flags); 052: the lead NPC's sinking seen by camera and lidar | as data allows; 052's item about 1 week | 053's and 052's own acceptance |
| **C9. Every car on the sweep** (issue 077's option B; registered 2026-11-20, the user's choice; not started) | aib's default `wheel_query` becomes `sweep` (with its bump stop, landed opt-in in 077), so every Isaac car climbs a curb. The mud classes (047 S5, 053, 054; fitted under the raycast) are refitted under the sweep. The cause of the sweep's yaw-rate chatter on a straight stop on mud is found and removed | 2-3 weeks (estimate) | 055's mud pad back within the fits' tolerances; it stands today at mud_circle 21.3 m off its line against -1.1 under the raycast, mud_dlc peak sideslip 10.7 against 20.8 deg, mud_sine heading change -32 against -42 deg; no yaw rate on `mud_brake` (the sweep's chatters by about 0.5 deg/s); dry and wet within 055's tolerances; aib's slope matrix, haruna_down, isaac_soil and the road_physics example unchanged |

#### C1: the road record (done 2026-11-20)

scensim_isaac_world 87e0ea1 (`road_record`, `road_layer.parse`), pins f00f02a2;
[reference: road physics](../reference/road-physics.md), "The section along the road".

- `road_detail.yaml` takes `schema: 1` (absent: 1; a newer one is refused, naming the update)
  and, per corridor, `section:` constants or `stations: <file>.npz` beside it. Every field
  has a default, a range and a meaning (`road_detail keys`); every problem is listed with
  where it is (the corridor, the field, the station).
- Today's road layer shapes the road with one symmetric section. A record it cannot express
  yet (banked, a lip, an offset crown, a shape that changes along the road or between the
  sides) is refused when the world loads, naming what differs; `road_detail check` notes it
  instead. `kappa_v`, the surfaces, the barrier and the hazard are carried, unread by Isaac
  until C3 and C5.
- Exit check: the detail tiles (surface heights and zones, sha256 over every tile within 4 m
  of each corridor's first 40 m) are byte-identical before and after for both examples
  (`proving_ground` d4a5a16f..., `town01` 429148cc...) and the stages dataset's `road_town`
  (429148cc..., the same road as the example). A constant record written as an `.npz` makes
  the same tiles as its YAML constants (test). Tests: 13 new (`test_road_record`), the world
  server's 287 pass.

#### C2: one class table (done 2026-11-20)

scensim_world_protocol 2519aca (the land_pin cascade bumped scensim_carla_world 4d95440 and
scensim_isaac_world e746674, pins 3f0f24fa), scensim_isaac_world 51a95b4 (pins 7aad5216).

- The table is `scensim_world_server/surface_classes.yaml`: package data
  (`scensim_world_server.classes.SURFACE_CLASSES`, what the Isaac surfaces read by default)
  and `share/scensim_world_server/config/surface_classes.yaml` for a world server that is not
  Python (C7). The Isaac world server's `config/` copy is gone; a map's own `classes:` in
  `surfaces.yaml` still wins.
- A road record's `shoulder_surface` and `runoff_surface` must be classes of the map's table:
  checked when the world server registers its maps, at every `LoadWorld`, and by
  `road_detail check`, naming the classes the table has.
- Exit check, adjusted: the plan's live check was the Town01 soil, mud and snow scenarios,
  but Town01 on Isaac does not render on 118 (driver 615.71.09, issue 005; 139's host). In
  its place: the moved table loads to an object equal to the old one (12 classes; the files
  differ only in the header comment); the installed build (j021 at 7aad5216) finds it, and
  `surfaces check` and `road_detail check` pass on the installed Town01 example; a live
  `haruna_down` on Isaac, the world server loading the course's `surfaces.yaml` with the
  shared table, passed (381.4 s simulated, 0 contacts, 118). An unknown class in a zone or
  a section is refused (tests). Tests: 3 new, the world server's 290 pass, the shell's 36.

#### C3: the course builder writes the record (done 2026-11-20)

scensim_isaac_world 98a5d8c (`course/record.py`, the builder's `record` step), pins 4c67e51d.

- The step runs after `geometry`, or alone from `course/centreline.npz` and
  `course/meshes.npz` with no fetch. It writes `course/road_detail.yaml` and
  `course/section.npz`: the builder's own section (level, the lanes and the shoulder, no lip
  or ditch), `kappa_v` from the smoothed profile, the centreline in the `.npz` (a record may
  now carry `x`, `y`, `z` in place of the YAML's `centreline`), and per side what lies past
  the edge from one classifier: `barrier` where props' rail rule puts a rail (at
  `barrier_offset`), else `runoff` at 1V:4H or flatter and `ditch` steeper, down or up (a cut
  face; 069 has no class of its own for it). A closed course repeats its first station.
- It is the course's record, in `course/`: the world server reads a map's road detail from
  `<map dir>/road_detail.yaml` only, so nothing changes in Isaac. Putting a course's record
  under the road layer (its contact, the ribbon from the record) is C5's.
- `props.guardrails` places the rails from the record; `usd` reads it and names the step
  when it is missing.
- Exit check: on the published Haruna and Tsukuba data (fff4cb0b) the rails from the record
  are identical to the old rule's, every segment exactly, at segment lengths of 1 to 6 m
  (Haruna 92 segments at 4 m, Tsukuba 46), so the published worlds need no rebuild and
  `haruna_down` drives the same world (it passed twice today on it). Haruna: 3055 stations,
  1527 m; left runoff 2285, ditch 414, barrier 356; right 2555, 122, 378. Tsukuba: 4285
  stations, 2142 m, left runoff 4056, barrier 229; right 4137, 148. `road_detail check`
  passes on both. Tests: 8 new (`test_course_record`, with the old rule frozen in it), the
  world server's 298; the full `just test` from `env -i` passed (with main's one-line
  justfile fix for C2's table path applied locally until 241's lands).
- The dataset revision is prepared on NAS home, `2026-11-20 086 C3 course road records
  (118)/`: the two courses' `road_detail.yaml` and `section.npz`, README, SHA256SUMS.
  Publishing it (with a new tag) is the user's.

#### C4: the scenario chooses its ground (landed 2026-11-20)

scensim_isaac_world 6177ced (pins cebb5557), scensim 82787b91; 056's steps 1-4.

- `scensim.surface_map=<name>` in a `RoadCondition` loads the map's `surfaces/<name>.yaml`
  (the testbench state's first) instead of its own `surfaces.yaml`, only while no wheel has
  driven on soil since the load or the last map: the old map's soil ground comes off, the new
  one's is built and settled, its rut sets live in `surfaces/<name>/ruts/`, and the rest of
  the condition is checked against it. It stays until a release, a new owner (both back to the
  world's own map) or the next `LoadWorld`. `scensim.default.<Label>=<class>` sets one ground
  label's class for the scenario, friction only. Every named map is checked when the server
  registers its maps, and `surfaces check <map dir>` checks them too.
- scensim: `ground.<map>.surface_maps: {<name>: <file>}` links each into
  `<state>/<map>/surfaces/<name>.yaml` at stack start (and removes links no longer named).
- The soil scenarios of 047, 052 and 054 moved from `scenarios/surfaces/` into the testbench
  `isaac_soil` (077's inventory item 19, blocked on per-scenario ground until now): each names
  its map in its Init and takes the stack's vehicle catalog; suite `soil` runs 053 step 5's set
  (soil, mud, snow) and the zones. `town01_dry` now opts in to `mud_wet` as the other mud maps
  do (refused since 053 flagged it). `scensim project check isaac_soil`: ok; all 11 maps pass
  `surfaces check`.
- Checks: tests 7 new in the world server (305), 2 in scensim; the full `just test` from
  `env -i` passed. Live on 118 (Town01 does not render there), the whole path on Haruna: a
  local testbench's `surface_maps` linked `state/haruna/surfaces/haruna_verge.yaml`, a copy
  of `haruna_down` named it with `scensim.default.SideWalk=gravel` in its Init, the world
  server logged the named map and the condition, and the run passed (381.4 s, 0 contacts).
- Open: 056 step 5 and its acceptance, `isaac_soil`'s suite on Town01 one after another on one
  world server, on 139 (asked of 133); and 056's "one scenario setting a label class beside a
  road it leaves" has no Town01 scenario yet.

### C5's steps (approved by 133, 2026-11-23)

- **C5a, the road layer per station.** `road_detail.StationSection` interpolates a record's
  section along the road: the bank, the crown line's offset, each side's crown, shoulder,
  foreslope, ditch and backslope, and the lip. A constant, symmetric, level record stays
  `road_detail.Section`. The layer no longer refuses a record it could not shape, nor takes a
  record's first station's left side with a note. Done 2026-11-23 (scensim_isaac_world
  ea35f35): 8 tests, the world server's 339 pass. Haruna's and Tsukuba's published records are
  both level (C3's builder writes a level section with no lip), so they still reduce to one
  `Section` and give the same road. A per-station corridor's tile takes 0.07 s against 0.043.
- **C5b, the ribbon from the record** (done 2026-11-23, results below). The course meshes tilt
  each strip by bank and crown, so PhysX's base road carries the cross slope, and the layer
  adds only what the mesh does not. Check: Isaac's road height and cross slope against the
  record at every station (within 5 mm and 0.1 deg), and midway between stations against the
  layer's own interpolation, so the mesh and the layer agree where the record says nothing. The
  nonzero-crown exit runs on a synthetic fixture course built by the same pipeline from a
  fixture centreline: a stated crown (2 to 3 %), a bank rising from 0 to 6 % through a bend,
  and a lip segment for C5c, driven with haruna_down's controller and checks. Haruna's and
  Tsukuba's records stay level: their only elevation source, GSI's 5 m DEM, cannot resolve
  either (one or two samples across a 6.5 m carriageway, a vertical error of about 0.3 m
  against a crown's 6 cm or a hairpin's 0.4 m of superelevation). A record gains a crown or
  bank only from a source that resolves it (a lidar point cloud, a survey), named in the
  record.
- **C5c, the lip and the strips.** The lip as a step in the mesh at the carriageway's edge, and
  the shoulder and run-off as surface zones from the record (C2's class table). Check: the lip
  re-entry fixtures, 5, 10 and 15 cm at 90, 45 and 30 deg. Each case's expected outcome
  (re-enters or held) is written into the fixture file from the record's rule before any run.
- **C5d, Autoware's maps from the same meshes.** The point cloud and the lanelet heights are
  regenerated from C5b's meshes, divided when large. Check: lanelet heights against the mesh
  within 5 mm; NDT holds on haruna_down.

C5's exit is 086's row. aib's slope matrix and haruna_down run against main's baseline on the
same host and GPU, so "unchanged" is a paired comparison. Every Isaac run is on 118's GPU0;
GPU1 stays with 094's training seeds.

#### C5b's fixture course (spec written 2026-11-23, before it is built)

A course with no OSM, DEM or photo: `courses/fixture_c5.yaml` names its centreline and section
as segments, and the builder's `centreline`, `geometry`, `record`, `maps` and `scenario` steps
run on it as on Haruna. Its record is the spec below, not a measurement; the file says so.

- **Frame.** An origin at (36.0, 140.0), alt 0, so the map frame and its projector work as
  for a real course; the yaml names it a fixture's arbitrary datum, not a place. Terrain: the road's own profile under it, flat across, 0.30 m below the
  formation at the section's foot and blending as `geometry.terrain` does; the photo is a
  plain grey image.
- **Plan and profile.** An open course, 510 m, a constant grade of -3 % (downhill, as
  haruna_down is). 2 lanes of 3.25 m, a 0.75 m shoulder, as Haruna's.

  | s (m) | plan | bank | crown, left / right | crown line | lip (right) |
  |---|---|---|---|---|---|
  | 0-150 | straight | 0 | 2.5 % / 2.5 % | centre | none |
  | 150-210 | clothoid, curvature 0 to 1/60 m | 0 to 6 %, linear | 2.5 % to 0, linear | centre | none |
  | 210-300 | arc, R 60 m, left (86 deg) | 6 % (inside, left, low) | 0 / 0 | centre | none |
  | 300-360 | clothoid, 1/60 m to 0 | 6 % to 0, linear | 0 to 2 % / 0 to 3 %, linear | 0 to +0.5 m (left), linear | none |
  | 360-510 | straight | 0 | 2.0 % / 3.0 % | +0.5 m | 0.10 m at 90 deg over s 420-480, its height ramped over 2 m at each end |

  So the course holds a symmetric crown, a superelevation runoff through a bend, a full
  bank, an offset and asymmetric crown, and one lip. C5c's lip fixtures (5, 10, 15 cm at 90,
  45, 30 deg) are their own courses or lanes, not this one.
- **Stations.** The record has a station at every centreline point (0.5 m, `centreline.STEP`),
  its values linear in s between the table's rows. Midway is the point between two stations.
- **Mesh.** `geometry.ribbon` takes the record: each row of the road ribbon at offset v is
  lifted by the record's section height at (u, v), with breaklines (rows) at the crown line,
  at the carriageway's edge and, where there is a lip, at both ends of its face, besides the
  0.5 m strips. The map's `road_detail.yaml` says the mesh carries the section, so the layer
  adds only what the mesh does not (its features and zones), not the section a second time.
  Haruna and Tsukuba, level records, give the same mesh as today (a vertex check).
- **Checks, offline (no GPU).** On the mesh's triangles, across the paved width every
  0.25 m and 2 cm each side of every breakline, at every station and every midway point:
  height within 5 mm of the record's section (`StationSection.height_uv`, the layer's own
  interpolation), and the cross slope of each half carriageway within 0.1 deg. Points on a
  lip's face (within 1 cm of it in plan) are left out of the height check. The same grid
  against the road layer's tiles for the record (C5a's 2e-3 m tile check, now on a banked
  record).
- **Checks, Isaac (GPU0).** PhysX scene queries straight down on the same grid give Isaac's
  road height: within 5 mm and 0.1 deg of the record at every station, and of the layer's
  interpolation midway. Then the course driven with haruna_down's controller and checks
  (speed limit 40 km/h): it passes, which is C5's "haruna_down passes on a course with a
  nonzero crown". On the banked arc the body's measured roll and its lateral acceleration
  along the road surface are checked against the record's, v^2/R cos(theta) - g sin(theta)
  with theta the bank, so the tilt is shown to reach PhysX's contact, not only its mesh. aib's slope matrix and haruna_down on Haruna, paired against main's on GPU0.
- **Finding (2026-11-23): the terrain stood above a lip's shoulder.** Isaac's first check had
  95 rays on the shoulder below the 10 cm lip hitting the terrain, not the road: the
  terrain's 2 m triangles, cut to the road's height at their corners, spanned the step and
  stood above the dropped shoulder between them. Under the road the terrain is now cut to
  the lowest the road comes within a cell and a half (3 m), and past it to the road's edge,
  as before; the rerun had no ray off the road. A course cut to a level road had no step
  for a triangle to span.

#### C5b's results (2026-11-23, 118, GPU0)

scensim_isaac_world b5de87b: `course/fixture.py`, `geometry.ribbon` taking the record,
`course/check.py` and `course/isaac_check.py` (the geometry), `course/ego_trace.py` (a
testbench attachment writing the ego's truth), `course/arc_drive.py` (aib's car through the
bend without Autoware) and `course/arc_check.py` (a trace against the record), and
road_detail's `section_in_base`. The
fixture builds in 3 s: 510 m, a 143.2 deg turn, R 60 m. Logs: NAS "2026-11-23 086 C5b fixture
course (118)".

| check | points | at stations | midway | limit |
|---|---|---|---|---|
| the road mesh against the record (offline) | 97968 | 0.000 mm, 0.0000 deg | 0.089 mm, 0.0000 deg | 5 mm, 0.1 deg |
| the road layer's tiles against the record (offline) | 92101 | 0.54 mm | 0.54 mm | 2 mm |
| Isaac's road by PhysX's rays against the record | 97968, none off the road | 0.003 mm, 0.0001 deg | 0.089 mm, 0.0001 deg | 5 mm, 0.1 deg |

The layer's check leaves out a tile cell and a half at the paved edge, where the record's
backslope back to the ground begins (1V:2H; a 5 cm cell rounds that kink by up to 7 mm).

The drive, against outcomes written before each run (`EXPECTED.md` in the logs):

| | speed on the arc | straight roll | arc roll | arc less straight | lateral force on the arc | if level |
|---|---|---|---|---|---|---|
| expected | | -1.43 +-0.5 deg | -3.43 +-1.0 deg | -2.0 +-1.0 deg | v w cos(theta) - g sin(theta) +-0.2 m/s^2 | v w |
| Autoware's Model 3, scensim run 2026-11-23T06-02-47_fixture_c5_down_r0, passed | 4.16 m/s | -1.48 | -3.55 | -2.07 | -0.310 against -0.290 | +0.298 |
| aib's Model 3 without Autoware, `arc_drive` at 11.1 m/s (arc40b) | 11.37 m/s | -1.53 | -2.84 | -1.31 | +1.726 against +1.623 | +2.214 |

**Finding: Autoware takes the arc at 4 m/s**, far under the course's 40 km/h: its velocity
smoother holds the lateral acceleration to 1.0 m/s^2 (`lateral_acceleration_limits` in
Autoware 1.5's velocity_smoother.param.yaml), so on Autoware a curve's speed is the
smoother's, not the map's, and a check that needs a curve's v^2/R must drive without it. So the 40 km/h case drove aib's PhysX car (the ego config's rig, as aib.steptest
builds it) with a pure pursuit and a speed hold. In both, the bank's g sin(theta) (0.59 m/s^2)
reaches PhysX's contact, not only the mesh.

#### C5c's fixtures (spec written 2026-11-23, approved by 133 the same day, before they are built)

Two parts: the lip re-entry fixtures, and the record's shoulder and run-off strips as surface
zones.

- **The lip course, `fixture_c5c`.** One straight, level course (grade 0), built by C5b's
  fixture builder: 2 x 3.25 m lanes, crown 2 % each side about the centreline, left shoulder
  0.75 m, right shoulder 2.0 m (wide enough for the right wheels with the left ones on the
  pavement). Eleven 120 m segments, each with its own right lip, the lip's height ramped over
  2 m between segments:

  | segment | lip (right) | face | the record's rule says |
  |---|---|---|---|
  | 0, control | none | | re-enters |
  | 1 | 5 cm | 90 deg | boundary (not over 5 cm, but about) |
  | 2, 3 | 5 cm | 45, 30 deg | re-enters (not over 5 cm) |
  | 4 | 10 cm | 90 deg | **held** |
  | 5 | 10 cm | 45 deg | boundary (not steeper than 45 deg, but at it) |
  | 6 | 10 cm | 30 deg | re-enters (face not steeper than 45 deg) |
  | 7 | 15 cm | 90 deg | **held** |
  | 8 | 15 cm | 45 deg | boundary |
  | 9 | 15 cm | 30 deg | re-enters |
  | 10, strips | none | | the right shoulder `gravel`, a 3 m `grass` run-off past it |

  The rule is 069's `lip` class: `lip_h` over about 5 cm with a face steeper than 45 deg; a
  lip that is not one re-enters, one that is holds a tyre on a shallow re-entry (scrubs).
  The fixture file holds each segment's expected outcome as a column, written before any
  run. So the fixture's table gains `lip_angle_right` and `shoulder_right` columns, and
  `shoulder_surface_right`, `runoff_len_right` and `runoff_surface_right` per segment.
- **The re-entry drive.** aib's Model 3 without Autoware, as C5b's `arc_drive` (the ego
  config's rig, a pure pursuit, a speed hold), at 15.6 m/s (35 mph, the speed at which Zimmer
  and Ivey found a vertical 11 cm edge unsafe). Each case starts 10 m into its segment with
  the right wheels' centres 0.5 m past the carriageway's edge and the left ones on the
  pavement, runs 40 m parallel to the edge, then follows a line at 4 deg back toward the road
  to the right lane's middle. One Isaac process drives all eleven segments (teleporting
  between them), once with aib's default `wheel_query: raycast` and once with `sweep` (C9's),
  on 118's GPU0. The teleport sets the car's velocity as well as its pose (issue 110), and each
  case logs its actual start speed and lateral offset: a case more than 0.1 m/s or 5 cm off is
  refused, not classified. Before the parallel leg each case also records whether its right
  wheels are on the shoulder (in contact with it, not hanging), one check line per case.
  At 15.6 m/s and 4 deg the lateral speed is about 1.09 m/s, so the control's right front
  wheel crosses the edge about 0.46 s after the turn-in.
- **Outcome.** The time the right front wheel's centre crosses the carriageway's edge, less
  the control's (the same drive with no lip): **re-enters** when it is 0.3 s or less,
  **held** when more, or when it never crosses within 4 s. Reported beside it, not judged:
  the peak yaw rate and lateral acceleration in the 1 s after the crossing, against the
  control's (the yaw spike), and the body's roll as the wheel climbs.
- **What the plant is expected to do.** The survey's inference (not measured): PhysX's wheel
  finds the ground with a ray or a sweep and has no sidewall, so it may climb every lip,
  re-entering where the rule says held. If Isaac re-enters at 10 or 15 cm at 90 deg, that is
  the finding 066 R8 named: a lateral edge force in R5's corner-force layer is then the fix,
  planned as its own step, not part of C5c. A rule-to-plant mismatch is a result, not a
  failed check. The three boundary cases are reported but counted neither as agreements nor
  as mismatches. C5c's check is that every case ran and is classified, and that the control
  crosses where its path says (within 0.3 s).
- **The strips as zones.** At load the surface layer turns the record's `shoulder_surface`
  and `runoff_surface` into zones: for each side, each run of stations with the same
  non-empty class becomes one polygon, from the carriageway's edge to the shoulder's end
  (shoulder), and from there `runoff_len` on (run-off); ids `record_<side>_shoulder_<n>` and
  `record_<side>_runoff_<n>`, so a scenario can name them as any zone. They lie under the
  map's own zones: a map's zone wins where they overlap. Checks: offline, a point on each
  strip reads its class and a point on the carriageway the map's; in Isaac, on segment 10
  the right wheels read `gravel` (wheels.py's `class` and `zone`) while they are on the
  shoulder, and the left ones the reference class.

**As built, where it differs from the spec above** (told to 133 with the results):

- aib's teleport puts the car at rest (`Vehicle.teleport` zeroes the body's velocity and the
  wheels' state), so a case does not start at speed. It starts at rest 5 m into its segment
  on the shoulder line, drives up to 15.6 m/s over 60 m along it, and the start check
  (speed within 0.1 m/s, lateral offset within 5 cm, the right wheels on the shoulder) is
  made where the 40 m parallel leg begins. The segments are 200 m, not 120 m, to hold that.
  The speed hold has an integral term, taken only within 1 m/s of the target: without one
  the cars started 0.09 m/s slow, and with one wound up from rest, 1.27 m/s fast (both seen in
  smoke runs, both refused or near it).
- The leg after the turn-in is 80 m (5.1 s at 15.6 m/s), over the 4 s held window.
- Both shoulders are 2.0 m: the course builder's mesh takes one shoulder width.
- The course's record is in `course/` (C3), not at `<map dir>/road_detail.yaml`, so the world
  server loads no road layer for a course and its strips reach a scenario only on a map with
  a road detail. `lip_drive` builds the surface layer as the server does
  (`SurfaceLayer.add_record_zones` over `road_layer.strip_zones`) on the map's own surface
  map.

#### C5c's results (2026-11-23, 118, GPU0)

scensim_isaac_world 086-c5c (`courses/fixture_c5c.yaml`, `course.lip_drive`,
`course.lip_check`, `road_layer.strip_zones`, `SurfaceLayer.add_record_zones`). Logs and
data: NAS "2026-11-23 086 C5c lip fixtures (118)".

- **The road.** The lip course's mesh against its record offline, and Isaac's road by
  510458 PhysX rays (32049 on a lip's face left out), 0 missing: both pass C5b's limits.
- **The starts.** All 22 cases started right: speed 15.638 to 15.641 m/s, lateral offset
  -0.010 to -0.015 m, both right wheels on the shoulder at its height.
- **The control** crossed 0.368 s (raycast) and 0.349 s (sweep) after the turn-in, against
  its line's 0.264 s (the front axle leads the base): within 0.3 s.
- **The strips.** On segment 10 the right wheels read `gravel` in `record_right_shoulder_1`
  through the parallel leg, the left wheels `asphalt` and no zone (both queries).

The lips, the right front wheel's crossing after the control's (s; held: none within 4 s),
then the peak lateral acceleration in the 1 s after it less the control's (m/s^2):

| segment | lip | face | rule | raycast | | sweep | |
|---|---|---|---|---|---|---|---|
| 1 | 5 cm | 90 | boundary | re-enters -0.025 | +1.48 | re-enters +0.023 | +0.02 |
| 2 | 5 cm | 45 | re-enters | re-enters -0.006 | +0.09 | re-enters +0.037 | +0.40 |
| 3 | 5 cm | 30 | re-enters | re-enters 0.000 | +0.78 | re-enters +0.025 | +0.59 |
| 4 | 10 cm | 90 | **held** | **re-enters** +0.017 | +1.39 | **re-enters** +0.032 | +1.95 |
| 5 | 10 cm | 45 | boundary | re-enters +0.045 | +1.41 | re-enters +0.077 | +1.36 |
| 6 | 10 cm | 30 | re-enters | re-enters +0.067 | +1.15 | re-enters +0.060 | +1.28 |
| 7 | 15 cm | 90 | **held** | held, by artefact (below) | | **re-enters** +0.057 | +4.68 |
| 8 | 15 cm | 45 | boundary | re-enters +0.077 | +2.19 | re-enters +0.103 | +3.46 |
| 9 | 15 cm | 30 | re-enters | re-enters +0.086 | +2.16 | re-enters +0.157 | +2.25 |

Raycast: 6 agree, 1 mismatch, 1 held by artefact (15 cm, 90 deg: issue 077's, below; not
counted as an agreement), 3 boundary. Sweep: 6 agree, 2 mismatches, 3 boundary. No case
showed the yaw spike: the peak yaw rate after the crossing was within 0.06 rad/s of the
control's in every case. The body's roll about the crossing grew with the lip, 1.5 deg on
the control to 5 deg at 10 cm and 7 deg at 15 cm.

- **Finding: Isaac's car climbs a vertical 10 cm lip it should be held by**, with both wheel
  queries, at 4 deg and 15.6 m/s, 0.02-0.03 s later than with no lip, and no yaw spike. The
  survey's inference holds for the sweep at 15 cm too. The lateral edge force 066 R8 named
  is its fix, as its own step, not C5c's.
- **Finding: the raycast's hold at 15 cm is not a tyre's.** Its right front wheel ran 4 cm
  outside the edge for the whole window with its ray's hit at the face's foot (v -3.2509, the
  1 mm-wide face at -3.250 to -3.251), on the shoulder: issue 077's mechanism, the ray taking
  a sharp face as the ground. So it is counted as held by artefact, not as the rule's held,
  and the sweep's re-entries are the plant's real answer: it has no sidewall to scrub with.
- **Finding: the outcome depends on the speed, and each case was classified at one.** In the
  two smoke runs raycast held at 10 cm, 90 deg with start speeds of 15.51 m/s (the case ended
  2.4 s after the turn-in, the wheel still outside) and 16.87 m/s (held for 4.5 s, the whole
  window); in the full run, at 15.64 m/s, it climbed. So no case's class above is robust: each
  is one drive at one speed.
- **Next, beside 066 R8's edge force: a speed sweep** around 15.6 m/s for the lips at 90 deg
  (both wheel queries), to find where the outcome changes. Not run in C5c.

#### C5d's maps (spec written 2026-11-23, approved by 133 the same day, before they are built)

What there is: the course builder's `maps` step (`course/maps.py`, 058 C7) samples the point
cloud from `meshes.npz`, which since C5b carries the record's section, so the cloud already
sees the crown, the bank and the lip. The lanelets do not: every bound node's `ele` is the
centreline's height, at the carriageway's edges too. On fixture_c5's 6 % bank that puts an
edge bound 0.20 m off the road, and a 2.5 % crown 0.08 m. Haruna's and Tsukuba's records are
level, so their lanelets are right today. The cloud is one PCD; Haruna's divided map (issue
072: 100 m tiles and `pointcloud_map_metadata.yaml`, which the profile loads dynamically) was
divided by hand for the dataset, not by the builder.

- **Lanelet heights from the record.** Each bound node's `ele` is the record's height at its
  (u, v): the centreline's z plus `StationSection.height_uv(u, v)`, v the bound's offset
  (the lane edges at +-half_width, the centre line at 0). A level record gives the heights of
  today exactly (a test). The builder's `record` step runs before `maps`, so the record is
  there; a course without one is refused by name, as `record.load` does.
- **The cloud divided when large.** Over `DIVIDE_POINTS` (1,000,000) points the builder writes
  `pointcloud_map.pcd/` as 100 m tiles named `<course>_<i>_<j>.pcd` with
  `pointcloud_map_metadata.yaml`, issue 072's layout, every point kept; at or under it, one
  PCD as today. fixture_c5 (1.32 M points) and Haruna (about 15 M) are divided, so both runs
  below load dynamically, the path 072 proved on Haruna.
- **Checks, offline.** Every lanelet bound node's `ele`, and the point midway between each
  two consecutive nodes of a bound (linear, as Lanelet2 reads it), within 5 mm of the road
  mesh's height there (`check.mesh_height`, the triangles' barycentric height), on fixture_c5
  (banked, crowned, offset crown) and fixture_c5c (the lips: the right bound runs along the
  lip's top). The divided cloud holds the same points as the undivided one (count and each
  point once), each tile's points inside its 100 m cell, and the metadata names every tile.
- **Checks, Autoware on Isaac** (GPU0, `--capture standard`, each map rebuilt by the branch's
  builder):
  - `fixture_c5_down` (the nonzero crown course): the scenario passes, and the nvtl judge's
    rule (058 C9): NDT's nearest voxel transformation likelihood, its 5th percentile after
    the first 10 s, at least 2.5, over at least 50 m. And the localization's horizontal
    error against the truth (`/localization/kinematic_state` against the ego_trace
    attachment's pose, matched by simulation time): its 95th percentile at most 0.2 m,
    judged; its maximum reported beside it, not judged.
  - `haruna_down` on Haruna rebuilt by the builder (lanelets unchanged, the record level;
    the cloud divided by the builder in place of by hand): the scenario passes, NVTL and the
    pose error as above. Its lap time and contacts are reported beside issue 072's run on
    the dataset's map (382.4 s, 0 contacts), not judged: they depend on Autoware's planning,
    not only on the map. The rebuilt maps go to a new directory,
    `/mnt/renegade/aeon/isaac-ex/c5d/haruna` on 118; 072's hand-divided map
    (`/mnt/renegade/aeon/isaac-ex/haruna-072/dataset/haruna`, and the NAS copy) is left as
    it is, so 072's run stays reproducible.
- **Not in C5d.** Publishing a dataset revision with the rebuilt maps (the user's call);
  driving Tsukuba (its record is level, so its lanelets do not change; a rebuild divides its
  cloud by the same rule, untested by a run here); C5's exit pairing (aib's
  slope matrix and haruna_down against main's baseline, on the same host and GPU0), which
  follows C5d.

As built: the builder's `maps` step also runs alone on a published course (`<course.yaml>
<map dir> maps`, or `record maps`), from its saved centreline, meshes and record, with no
fetch; before it, a step list without `centreline` still fetched the DEM and photo tiles
(seen once on a copy of Haruna: public GSI tiles into its `raw/`, nothing rebuilt). The pose
judge is `scenarios/projects/courses/judges/pose_error.py`, beside `nvtl.py`.

#### C5d's results (2026-11-23, 118, GPU0)

scensim_isaac_world 33c6aae (`course/maps.py`, `course/check.py`'s lanelet and cloud
checks, the maps-only step). Logs and data: NAS "2026-11-23 086 C5d maps (118)". Runs on 118
in `/mnt/renegade/aeon/isaac-ex/c5d`, a local testbench workspace there.

- **Lanelets against the mesh** (`course.check`): fixture_c5's bound nodes within 0.42 mm,
  midway 0.88 mm (C5b's maps, the centreline's height across: 195 mm on the bank);
  fixture_c5c's within 0.20 mm (the right bound along the lips' top).
- **The divided clouds**: fixture_c5 16 tiles, 1,320,500 points; fixture_c5c 48 tiles,
  2,665,716; each tile in its cell, the metadata naming every tile, the count the build's.
- **Haruna rebuilt** (`record maps` on a copy of 072's map): the lanelets identical to 072's
  but for the generator's name (`swb_isaac_world` then); the cloud 15,788,823 points in the
  same 140 tiles with the same metadata, 123 tiles point for point and 17 road tiles differing
  by under 0.1 % of their points (the road surface sampled anew; terrain and props identical).
- **Autoware on Isaac** (Model 3, the scensim profile, `--stop-stack`; the stack w10c's build,
  scensim 61ad6d58 with scensim_isaac_world b5de87b and aib 23ef5fb, as each run's `result.json`
  records; the maps are the branch builder's, made offline):

  | run | maps | scenario | NVTL p05 (>= 2.5) | pose error p95 (<= 0.2 m) | max (reported) |
  |---|---|---|---|---|---|
  | haruna_down, 2026-11-23T10-29-29 | rebuilt | passed, 384.5 s, 0 contacts | 3.12 over 1470 m | **0.183, passes** | 0.202 |
  | fixture_c5_down, 2026-11-23T10-26-37 | rebuilt | passed | 3.31 over 451 m | **1.33, fails** | 1.38 |
  | fixture_c5_down (A/B), 2026-11-23T10-37-23 | C5b's | passed | 3.31 over 451 m | **1.29, fails** | 1.31 |

  haruna_down beside 072's run on the dataset's map (382.4 s, 0 contacts), reported, not
  judged. Its pose error passes with little margin: the p95 is 0.183 m against 0.2, and the
  maximum 0.202 m.
- **Finding: on fixture_c5 NDT does not hold the car's lateral position, and the check set in
  advance fails.** Autoware held its pose at the lane's middle (1.6-1.8 m left of the
  centreline) the whole run while the car, by the truth, ran from 0.3 to 2.9 m left (0.35 m
  from the left edge on the banked arc); along the road NDT trailed the truth by up to 0.6 m
  from the bend on. The same drive on C5b's maps fails the same way, so the cause is not the
  new maps but the course: a fixture has nothing beside the road for NDT to fix a lateral
  position by (flat ground 0.3 m below, no rails, trees or buildings), and a cloud without
  lateral features matches almost anywhere across the road, so NVTL stays high (3.31) while
  the pose is wrong. NVTL alone does not show a lateral error.

**Amendment, made after the results** (133, 2026-11-23, as with issue 106): the result above
stands as a failure of the rule written before the runs; the rule is not changed. C5d's map
checks pass and land. The fixture's localization becomes its own step, C5d2.

#### C5d2: the fixture with lateral features (spec written 2026-11-23, after C5d's results, before any run)

- **The course.** fixture_c5 with guardrails and trees, through the course builder's props
  step as a real course gets them (`course/props.py`, the USD step's guardrails and trees,
  their points in `props_points.npy` and so in the cloud). The guardrails stand at the
  record's `barrier_offset`, which fixture_c5's record has none of today: the fixture's table
  gains `barrier_offset_left` and `barrier_offset_right` columns, a rail each side 0.5 m past
  the shoulder over the whole course, so NDT has a lateral feature on both sides. The trees
  are the props step's, at its spacing and band beside the road. The plan,
  section, lanes and lip are C5b's; the course is built anew into its own map directory.
- **The check, the same rule as C5d's, written before any run:** fixture_c5_down under
  Autoware on Isaac (GPU0, the maps rebuilt by the builder, `--stop-stack`): the scenario
  passes, NVTL p05 after the first 10 s at least 2.5 over at least 50 m, and the
  localization's horizontal error against the truth at most 0.2 m at its 95th percentile (the
  maximum reported, not judged).
- **And kept from C5b**, since the props change the course: the road mesh against the record
  (`course.check`) and Isaac's road (`isaac_check`) within C5b's limits, and the lanelets
  within 5 mm.
- Not started until C5d lands.

#### C5d2's results (2026-11-23, 118, GPU0)

scensim_isaac_world 086-c5d2 (41a0102: the fixture's `barrier_offset_*` columns, `photo:
forest`, `courses/fixture_c5d2.yaml`). Logs and data: NAS "2026-11-23 086 C5d2 fixture with
lateral features (118)". Run on 118 in `/mnt/renegade/aeon/isaac-ex/c5d2`.

- **The course**: C5b's road with 340 guardrail segments (1020 m, both sides at 4.5 m) and
  1398 trees; the cloud 6,011,964 points in 16 tiles (C5d's 1,320,500 without them).
- **Kept from C5b**: the mesh against the record 0.000 mm at the stations; Isaac's road by
  97968 rays, 0 missing, passes; the lanelets within 0.42 mm (nodes) and 0.88 mm (midway).
- **Autoware on Isaac** (the stack w10c's build, scensim 61ad6d58, as for C5d; Model 3, the
  scensim profile, C5d's fixture scenario with the map's
  name changed: the builder's own names the drift Mustang; run 2026-11-23T12-03-03):

  | | scenario | NVTL p05 (>= 2.5) | pose error p95 (<= 0.2 m) | median | max (reported) |
  |---|---|---|---|---|---|
  | fixture_c5d2_down | passed, 127.4 s, 0 contacts | 3.08 over 451 m | **0.103, passes** | 0.054 | 0.127 |
  | C5d's fixture_c5_down, no rails or trees | passed | 3.31 over 451 m | 1.33, fails | 0.75 | 1.38 |

- **Finding: with lateral features NDT holds the pose on the crowned, banked course**, within
  the rule set before the runs and with more margin than Haruna (0.103 against 0.183 m). So
  C5d's failure was the fixture's, as its A/B said.

**Amendment, made after the results** (133, 2026-11-23): this run counts for C5's exit item
"`haruna_down` passes on a course with a nonzero crown". The item named haruna_down, but
Haruna's published record is level (GSI's 5 m DEM cannot resolve a crown or a bank, C5's
steps above), so the crowned, banked fixture with lateral features stands in for it. The
course is synthetic, not a measured road, and its guardrails stand at the centreline's height
(below). NVTL was lower with the features (3.08 against 3.31) while the pose was right: a high
  NVTL on a featureless map is no sign of a held pose.
- As built: the guardrails stand at the centreline's height (`props.guardrails`, as on every
  course), so on the 6 % bank a rail is up to about 0.27 m off the ground at 4.5 m; NDT needed
  them only beside the road. The commit's message lost "`photo: forest`" to the shell (it was
  already pushed to the branch; no force-push).

#### C5's exit pairing (2026-11-23, 118, GPU0)

A = scensim main 8965a06a, the last main before C5a's pin; B = main f98f1cd1, after C5d. Both
full builds on 118 (A on the root disk, `/var/tmp/aeon/pair-a`: `/mnt/renegade` was 99 % full),
run one after the other on GPU0. Below C5, A and B also differ in aib (401bd27 to 3cd2b7d),
sim_vehicle_ecu (ef6bfd8 to 99505b0) and sim_vehicle_spec (21bf3dc to 9ceb8cb).

- **aib's slope matrix** (`aib.steptest`, every test): it builds the car on a flat ground plane
  with gravity tilted and never loads the world server, so it cannot see C5's changes; the
  pairing's real C5 check is haruna_down. All 17 tests both have are identical, A against B
  (B adds `regen_30`).
- **haruna_down** on the published Haruna (dataset tag b12857ee, issue 072's 140 tiles), with
  Autoware's Model 3: none of C5's code acts on this map (no `road_detail.yaml` in its map
  directory, its maps the dataset's), so a difference here would come from below C5.

  **The first haruna pairing is void.** Its four runs went through one testbench workspace
  built with B's install sourced, so that workspace's `setup.bash` chained
  `/mnt/renegade/aeon/gate-c5c/install` (B) and put it over whatever the run script had sourced
  first (CLAUDE.md's overlay-order trap). Every run's `result.json` records scensim f98f1cd1,
  the two "A" runs included: they were a mix of A's and B's paths, not A. Their numbers, kept
  for the record only:

  | run, as labelled | scensim recorded | scenario | NVTL p05 | pose error p95 | max |
  |---|---|---|---|---|---|
  | B, 2026-11-23T12-23-52 | f98f1cd1 | passed, 383.5 s, 0 contacts | 3.12 | 0.178 m | 0.2025 m |
  | "A", 2026-11-23T12-31-00 | f98f1cd1 (mixed) | passed, 385.5 s, 0 contacts | 3.12 | 0.115 m | 0.155 m |
  | B2, 2026-11-23T12-39-00 | f98f1cd1 | passed, 406.6 s, 0 contacts | 3.12 | 0.183 m | 0.2024 m |
  | "A2", 2026-11-23T12-46-32 | f98f1cd1 (mixed) | passed, 383.5 s, 0 contacts | 3.12 | 0.114 m | 0.151 m |

  The "real shift" first read from them, and issue 116 opened on it (its bisection, run through
  the same workspace, was on B's code throughout and was stopped), rest on a mixed overlay.
  Issue 116 waits on the clean pairing.

  **The clean pairing (written before its runs, 133):** one testbench workspace per side,
  built against that side's install only; `haruna.sh` refuses a run unless the live world
  server's and bridge's paths (`/proc/<pid>/exe` and command line) are under that side's
  install and the run's `result.json` names that side's scensim commit. Three runs per side,
  alternating. A real shift: the mean of B's three p95s at least 0.05 m above A's, and every B
  run above every A run; otherwise run-to-run spread. If no shift, issue 116 closes as "not
  reproduced; the premise came from a mixed overlay".
- **The clean pairing's result: run-to-run spread, no shift.** Every run passed `haruna.sh`'s
  check (the live bridge and world server under its own side's install, `result.json` naming
  its commit) and every scenario passed (0 contacts, NVTL p05 3.12):

  | run | scensim | pose error p95 | max | simulated |
  |---|---|---|---|---|
  | cB1, 2026-11-23T13-27-25 | f98f1cd1 | 0.181 m | 0.203 m | 388.5 s |
  | cA1, 2026-11-23T13-34-42 | 8965a06a | 0.182 m | 0.202 m | 386.5 s |
  | cB2, 2026-11-23T13-41-58 | f98f1cd1 | 0.126 m | 0.155 m | 387.5 s |
  | cA2, 2026-11-23T13-49-14 | 8965a06a | 0.184 m | 0.203 m | 394.5 s |
  | cB3, 2026-11-23T13-56-37 | f98f1cd1 | 0.180 m | 0.201 m | 385.5 s |
  | cA3, 2026-11-23T14-03-53 | 8965a06a | 0.185 m | 0.201 m | 391.5 s |

  B's mean p95 0.162 m against A's 0.184 m: B is not above A, so by the rule above there is
  no shift. The runs fall in two groups, about 0.18 m and about 0.12 m, on either side; the
  void pairing's mixed "A" runs were two of the lower. Issue 116 is closed: not reproduced, its
  premise came from a mixed overlay.
- **C5's exit, by the pairing:** aib's slope matrix unchanged (17 tests identical), and
  haruna_down unchanged by C5 (it passes on both sides alike). Haruna's pose error has little
  margin to the 0.2 m rule on both: four of the six clean runs had a maximum over 0.2 m (not
  judged), and most p95s are about 0.18 m. **Open observation, not an issue yet:** Haruna's
  pose error p95 is bimodal, about 0.12 m or about 0.18 m from run to run on either main, and 4
  of the 6 clean runs' maxima were over 0.2 m; its margin to the 0.2 m rule is thin.

### C6's steps (spec written 2026-11-23, before any run; for 133's approval)

C6 is the rest of 066 (R1's checks, R4 finished, R6, R7), now on the road record: a course the
builder makes, its section and hazards in `course/section.npz`, its road layer reading it, its
Autoware maps from C5d's builder. Every Isaac run on 118's GPU0 (GPU1 is 094's); every
A/B comparison in one testbench workspace per side, each run refused unless its live processes
and `result.json` name that side (C5's lesson). Four steps, each with its own spec, written
into its section before its runs, and its rule set before them:

- **C6a. The fixtures on a record course, and R1's checks.** Failed 2026-11-23 (below);
  C6a2 tests the causes. R0's nine lanes (5, 10, 15 cm
  cleats, the 8 cm pothole, 30 m of washboard, the kicker, the 20 cm boulder, the loose 10 kg
  rock) as a fixture course the builder makes (C5b's `fixture:` path), the lanes the road
  layer's features on its record, driven by `road_fixtures` through the world server's road
  layer (R5's contact). Check, 066's first acceptance item less wheel hop: the cleat force
  rising ahead of the hub, the pothole's unload then far-edge peak within 0.5 s, the landing
  spread over 10-30 ms, each fixture's peak load and body rise within 30 % of R0's 4 kHz
  reference. R1's cost line: PhysX's query and our contact with 1, 2 and 4 vehicles, frame
  p50 and p95.
- **C6b. Rocks on the record's road (R4 finished).** Rocks placed from the record (R4's
  size distribution along the edges, in the record's `runoff` and `ditch` strips, none on the
  carriageway unless the course asks) on Haruna rebuilt and on a fixture. Check: a 15 cm rock
  at 40 km/h lifts the wheel and pitches the body with no rigid-limit impulse; a boulder over
  the clearance strikes the skid plate; rocks under wheels move by the reaction force; R4's
  budget on an idle GPU0 (one ego frame p50 at most 5 ms over the same course without rocks,
  p95 under 45 ms; two egos keep real time at p50).
- **C6c. Wheel hop (R6).** A virtual unsprung mass per corner on a tire spring at the vehicle
  substep rate, between R5's effective road and the body. Check: a 10-15 Hz peak in the chassis
  and wheel-load spectra on C6a's washboard; grip loss on washboard rising with speed; 055's
  manoeuvre suite and aib's slope matrix unchanged on smooth road (paired, A/B as above).
- **C6d. Sensors and Autoware on the rough record road (R7).** Autoware on C6b's Haruna with
  rocks, its lanelets and cloud from C5d's builder (the lanelet map R4 lacked): motion BVH on,
  the lidar following the chassis, `scan_ground_filter` over the washboard and ruts. Check,
  paired (133, 2026-11-23: Haruna's pose error p95 already scatters between about 0.12 and
  0.18 m with maxima over 0.2 m on smooth road, so an absolute 0.2 m could fail for reasons
  that are not the rocks): three runs with rocks against three without, the same build, a
  testbench workspace per side. The rocks fail if their mean pose error p95 rises by 0.05 m or
  more, or if any run fails its scenario or NVTL p05 2.5. The absolute values are reported
  beside it, with false stops per km and the rock and pothole detection range.

C6's exit is 066's acceptance as these four steps hold it, plus aib's slope matrix and
haruna_down unchanged on smooth road, paired as C5's were. C6a's own spec (the fixture course's
table, the reference's numbers per lane, the runs) is written next, before its first run.

#### C6a's fixtures (spec written 2026-11-23, before any run; for 133's approval)

- **The course, `fixture_c6a`.** One straight, level fixture course (C5b's builder): 2 x
  3.25 m lanes, 0.75 m shoulders, a 2 % crown, the record's section in the base road as in
  C5b, and R0's fixtures as the road layer's features on the record's corridor, written into
  the course's `road_detail.yaml`:

  | s (m) | fixture | R0's lane | under |
  |---|---|---|---|
  | 100 | cleat 5 cm high, 0.2 m long, vertical edges | `cleat_05` | both tracks |
  | 200 | cleat 10 cm | `cleat_10` | both tracks |
  | 300 | cleat 15 cm | `cleat_15` | both tracks |
  | 400 | pothole 8 cm deep, 0.5 m long, 0.8 m wide, vertical edges | `pothole` | the left track |
  | 500-530 | washboard 2 cm peak to peak, 0.7 m pitch, no skew | `washboard` | both tracks |

  The road layer has no box-edged cleat (its water bars are cos^2 ridges) and places
  potholes at random: C6a adds `cleats` (u, height, length) and fixed potholes (u, depth,
  length, width, lateral centre) as road-detail features. R0's kicker (base geometry over
  5 m, which a one-grade fixture cannot hold), boulder and loose rock (rocks: C6b) are not in
  C6a.
- **The drive, `course.fixture_drive`.** aib's Model 3 with no Autoware, as `lip_drive` drives
  (the rig, a straight-line pursuit, a speed hold), the road layer built as the world server
  builds it (`road_layer.load` on the course's `road_detail.yaml`, `RoadLayer.before_substep`:
  R5's contact), on GPU0. Per PhysX step: each wheel's load from our contact, the body's
  height, pitch and vertical acceleration. Cases: cleat_05, cleat_10, cleat_15, pothole and
  washboard at 10 m/s; cleat_10 and washboard at 20 m/s; cleat_10 at 20 m/s from five start
  offsets 0.07 m apart (R0's question 1). A case starts at rest 60 m before its fixture and is
  checked at speed 10 m before it (C5c's start check: within 0.1 m/s and 5 cm).
- **The reference**, R0's quarter car at 4 kHz (`fixture_course.reference`, the rig's sprung
  413.6 kg, 41.8 kN/m, 3.74 kN s/m, travel 0.20 m, sag 0.097 m, a 0.37 m tire), computed before
  the runs; the front-left wheel:

  | case | peak load | body rise | first rise from the face | airborne | load min-max |
  |---|---|---|---|---|---|
  | cleat_05, 10 m/s | 13.3 kN | 2.6 cm | -0.18 m | 0.04 s | |
  | cleat_10, 10 m/s | 20.2 kN | 7.8 cm | -0.24 m | 0.12 s | |
  | cleat_10, 20 m/s | 24.0 kN | 5.1 cm | -0.24 m | 0.09 s | |
  | cleat_15, 10 m/s | 26.6 kN | 20.2 cm | -0.28 m | 0.30 s | |
  | pothole, 10 m/s | 10.1 kN | 0.2 cm | +0.38 m | 0.02 s | |
  | washboard, 10 m/s | | | | | 1.16-7.36 kN |
  | washboard, 20 m/s | | | | | 1.43-8.24 kN |

- **The check** (066's first acceptance item, less wheel hop, which is C6c's):
  - each cleat's peak load and body rise within 30 % of the reference's, and its load rising
    ahead of the hub (the first rise at a negative distance from the cleat's face);
  - the pothole: the left front wheel unloads (under 30 % of static) over the hole, then its
    far-edge peak within 0.5 s, the peak within 30 % of the reference's;
  - each landing after a wheel leaves the ground (load 0) spread over 10-30 ms (from the first
    load back to the landing's peak);
  - washboard: the load's minimum and maximum each within 30 % of the reference's;
  - cleat_10 at 20 m/s: no start offset misses the cleat (a peak at least twice static) or
    throws the car (body rise over three times the reference's, or pitch over 20 deg).
  - Reported, not judged (judged in C6b's budget): R1's cost line, frame p50 and p95 with 1, 2
    and 4 vehicles driving the course, PhysX's query and our contact.
- Not in C6a: the corner's wheel hop (C6c), and any A/B: C6a measures one build against the
  reference.
- **133's additions (approved with the spec, before any run):**
  - *Both wheel queries*, every case run with `wheel_query: raycast` and with `sweep`, as in
    C5c, a prediction beside each written now. 133's reading: a raycast wheel has no
    footprint, so it cannot feel a cleat ahead of the hub, and "load rising ahead of the hub"
    should fail under raycast. 118's prediction differs: on a course with a road layer,
    PhysX's query sees only the smooth base road (`road_layer`: the base under a tire's patch is
    a plane), and the cleat's load is our contact's (R5's tandem cam, a footprint over the
    effective road) whichever query PhysX runs, so both queries should pass alike and differ
    by little. Whichever holds is the result; a mismatch with a prediction is not a failed run.
  - *The rate*: PhysX steps at 60 Hz, three a 50 ms frame (`physics_dt` 1/60 s), the vehicle
    integrating 8 substeps a step (480 Hz, aib's `physx_substeps`); our contact runs once a
    PhysX step and its force holds for the step. The tyre load is logged at that rate, every
    PhysX step, the finest our contact has; PhysX's internal substeps are not reachable from
    Python. At 20 m/s a 0.2 m cleat lasts 10 ms, under one 16.7 ms step: each peak is reported
    with its sample count (the steps whose load is over twice static), and if a peak misses,
    the 60 Hz rate is named as a likely cause (R5's cam spreads the load over the footprint,
    which is what should carry it).
  - *The plant*: each run names the aib it used (its commit, from the workspace's
    `src/autoware_isaac_bridge`), since issue 108's grip fix lands meanwhile; loads hardly
    depend on friction.

#### C6a's result: failed (2026-11-23, 118)

Run as specified (siw `086-c6a`: 72082f5, 6596f9a, 02ced99; aib 23ef5fb, before issue 108's
grip fix; GPU0 shared with another job; logs on the NAS, "2026-11-23 086 C6a fixtures on a
record course (118)"). Two departures from the spec: the 20 m/s cases start 95 m before
their fixture, since 60 m cannot reach 20 m/s at the speed hold's 3 m/s^2 before the start
check; and the first raycast run refused two cases at that check (10.10 m/s, the hold
overshooting), so the hold was fixed (a ramped target) and both queries run again, every
start then within it. The check itself is as specified. Front-left wheel, reference, then
raycast / sweep:

| case | peak load (kN) | body rise (cm) | first rise (m) | samples over 2x static |
|---|---|---|---|---|
| cleat_05, 10 m/s | 13.3: 11.2 / 10.3 | 2.6: **1.2 / 1.2** | -0.18: -0.30 / -0.26 | 1 / 1 |
| cleat_10, 10 m/s | 20.2: 16.2 / 16.9 | 7.8: **5.3 / 4.9** | -0.24: -0.34 / -0.39 | 2 / 1 |
| cleat_10, 20 m/s | 24.0: 26.3 / 27.2 | 5.1: 5.6 / 6.0 | -0.24: -0.35 / -0.55 | 1 / 1 |
| cleat_15, 10 m/s | 26.6: 32.1 / 32.0 | 20.2: 21.6 / 20.3 | -0.28: -0.45 / -0.43 | 3 / 3 |

- The pothole: the wheel unloads to 0, the far-edge peak 10.3 / 10.3 kN (10.1) 33 ms later.
- Washboard at 10 m/s: 1.18-7.90 / 1.14-7.83 kN (1.16-7.36). At 20 m/s: **2.64** / **2.72**
  to 6.23 / 6.21 kN (1.43-8.24): the minimum fails.
- cleat_10 at 20 m/s from five offsets: peaks 23.6-28.0 / 17.2-28.1 kN, each in one or two
  samples; no miss, no throw.
- Landings: 36 / 33, spreads 15-38 / 15-42 ms, **six outside 10-30 ms** under each query,
  nearly all at 31-35 ms.
- The cost line (reported): frame p50/p95 7.3/10.3, 13.6/153.9 (a stall), 22.3/29.2 ms with
  1, 2, 4 cars under raycast; 7.4/9.6, 12.8/17.2, 21.9/27.3 ms under sweep; our contact
  1.4-2.4, 2.8-4.8 (raycast's two: 3.2/38.5), 5.4-8.0 ms.

**C6a failed**, judged without the rig's skid plate (C6b found the drives had none; its
first run repeats the cleats with it): body rise on the 5 and 10 cm cleats at 10 m/s, washboard's minimum at
20 m/s, and the landing spread. The rule is not amended after the result. Both queries put
the load ahead of the hub on every cleat and differ little: 118's prediction held, and 133's
(a raycast wheel cannot feel a cleat ahead of its hub) did not, since the cleat's load is our
contact's footprint whichever query PhysX runs. The causes are hypotheses, which C6a2 tests:
the 60 Hz rate (a load logged as each step's mean averages out washboard's 28.6 Hz troughs at
20 m/s, a 10 ms cleat falls into one or two steps, and a landing's spread is read to a step,
16.7 ms), and PhysX's corner lacking the reference's 42 kg unsprung mass (the body rise).

#### C6a2: testing C6a's causes (spec written 2026-11-23, before any run; for 133's approval)

- **The plant and the code**: aib after issue 108 (ff5e72b, the corrected grip), siw `086-c6a`
  rebased onto cb4d749 as `086-c6a2`; each run names both.
- **The rate**: C6a's 12 cases under both wheel queries at a physics rate of 60, 120 and
  240 Hz (`physics_dt` 1/60, 1/120, 1/240 s; 3, 6, 12 steps a 50 ms frame). aib's
  `physx_substeps` goes 8, 4, 2 so the vehicle's own integration stays at 480 Hz: only our
  contact's rate (once a PhysX step, its force held for the step) and the logging change.
  The tyre load is logged at every PhysX step, the finest our contact has.
- **The hypotheses, each judged on its own** (C6a's 30 % rule unchanged, its checks
  reported at each rate, C6a's verdict unchanged):
  - *H1, washboard's minimum is the rate*: washboard at 20 m/s's minimum falls with rate and
    is within 30 % of the reference's (at most 1.86 kN) at 240 Hz.
  - *H2, the offsets' spread is the rate*: cleat_10 at 20 m/s's five peaks, their range over
    their mean, at 240 Hz under half of 60 Hz's.
  - *H3, the landings are read to a step*: the landings at 31-35 ms, as a share of all, at
    240 Hz under half of 60 Hz's.
  - *H4, the body rise is the missing unsprung mass*: cleat_05's and cleat_10's at 10 m/s stay
    more than 30 % under the reference's at every rate, moving by less than 20 % of their
    60 Hz value between 60 and 240 Hz. If it holds, the shortfall goes to C6c; if the body
    rise reaches the band with rate, the cause was the rate.
  - 118's prediction: H1, H2, H3 and H4 hold.
- **The cost line again**: `fixture_cost` with 1, 2 and 4 cars under both queries at 60 Hz,
  on GPU0 with nothing else on it if the other session's job allows (`nvidia-smi` before each
  run, in the log), else as it is and said so; and 1 car at 120 and 240 Hz. Reported, not
  judged.
- **Approved by 133** (2026-11-23, as written): holding the vehicle's own integration at
  480 Hz while only our contact's and the logging's rate moves isolates the hypothesis. H1 to
  H4 are each judged alone; C6a's verdict stays failed.

#### C6a2's result (2026-11-23, 118)

siw `086-c6a2` (38ada7b), aib ff5e72b; GPU0 with nothing else on it in any run; every start
within the check; logs on the NAS, "2026-11-23 086 C6a2 rate test (118)". Raycast / sweep:

| | 60 Hz | 120 Hz | 240 Hz |
|---|---|---|---|
| washboard 20 m/s, min (kN; ref 1.43) | 2.62 / 2.66 | 1.97 / 1.95 | 1.77 / 1.76 |
| cleat_10 20 m/s, offsets' range / mean | 0.28 / 0.41 | 0.30 / 0.10 | 0.18 / 0.18 |
| landings at 31-35 ms, share | 0.18 / 0.13 | 0.05 / 0.08 | 0.03 / 0.00 |
| landings outside 10-30 ms | 7 / 6 | 2 / 3 | 1 / 1 |
| cleat_05 10 m/s, body rise (cm; ref 2.6) | 1.13 / 1.13 | 1.21 / 1.22 | 1.25 / 1.25 |
| cleat_10 10 m/s, body rise (cm; ref 7.8) | 5.28 / 5.37 | 5.48 / 5.43 | 5.73 / 5.68 |
| cleat_10 20 m/s, peak (kN; ref 24.0) | 17.1 / 27.7 | 28.9 / 39.5 | 48.9 / 43.6 |
| cleat_15 10 m/s, peak (kN; ref 26.6) | 28.5 / 30.7 | 31.3 / 40.6 | 52.7 / 49.7 |
| washboard 10 m/s, min (kN; ref 1.16) | 1.12 / 1.14 | 0.82 / 0.76 | 0.72 / 0.69 |

- **H1 holds** under both queries: washboard's minimum at 20 m/s falls with rate and is in
  the band at 240 Hz.
- **H2 holds under sweep and fails under raycast**: sweep's spread at 240 Hz is 0.45 of its
  60 Hz value, raycast's 0.62.
- **H3 holds** under both: the 31-35 ms cluster goes, and one landing a query stays outside
  10-30 ms at 240 Hz.
- **H4 fails** under both, by its own rule: cleat_10's body rise moves 6-9 % and reaches the
  band's edge (5.46 cm) at 120 Hz under raycast and at 240 Hz under both. cleat_05's stays half the
  reference at every rate, moving 11 %. The rate does not explain the shortfall, which
  stays near 30 % on cleat_10 and 50 % on cleat_05; the wheel mass is still the likely cause
  and C6c's to test, but H4 as written did not hold.
- **New, not predicted:** as the rate rises the peaks grow past the reference: cleat_10 at
  20 m/s and cleat_15 reach about twice it at 240 Hz, and washboard's minimum at 10 m/s falls
  under its band. At 60 Hz a step's mean hid this, so C6a's peak passes owed something to the
  averaging. Two readings, neither tested: our contact is harsher than the 4 kHz quarter car
  on a sharp edge, or its force held for a shorter step couples more stiffly with PhysX's
  corner. C6c (a wheel mass between them) is where it is tested.
- The cost line (reported; frame p50/p95 ms, our contact p50/p95 ms): at 60 Hz, raycast 1, 2,
  4 cars 9.1/14.6 (1.9/3.1), 19.6/28.8 (4.7/7.1), 34.1/45.6 (8.7/12.9); sweep 7.8/13.6
  (1.5/3.0), 13.1/17.8 (2.8/5.3), 22.3/27.7 (5.5/7.2). C6a's 2-car raycast stall did not
  recur, but raycast ran slower than sweep and than C6a's raycast with the same code, right
  after the docs gate's build ended, so its raycast-sweep gap is not a result. One car at 120
  and 240 Hz: 13.8/16.5 and 26.6/32.1 (raycast), 13.4/16.4 and 27.5/33.0 (sweep); our contact
  2.8/3.5 and 5.5/6.6: the frame's cost about doubles with each doubling of the rate.

#### C6a3: the peaks' growth with rate (spec written 2026-11-23, before any run; for 133's approval)

C6a2 found the sharp-edge peaks growing past the reference with rate. C6b's rock checks rest on
the same contact, so this comes before C6b (133); C6c keeps the unsprung mass.

- **The cases**: cleat_10 at 20 m/s, cleat_15 at 10 m/s and washboard at 10 m/s, under both
  wheel queries, at 480 Hz (24 PhysX steps a frame, aib's substeps 1: the vehicle's own
  integration still 480 Hz), beside C6a2's 60, 120 and 240 Hz runs of the same code and
  plant (siw `086-c6a2`, aib ff5e72b), which are not run again.
- **The measure, an impulse, not a peak.** For a cleat, the excess impulse J = the integral
  over time of max(load - static, 0), with the front-left hub from 1 m before the face to 1 m
  past the cleat's end (the landing excluded); static as `fixture_check` takes it. Our
  contact's logged load is its mean over the step, so J is its force's integral at any
  rate. For washboard, D = the mean of |load - static| with the hub on the washboard. The
  reference's, from R0's quarter car at 4 kHz (sampled at 500 Hz) with C6a's constants:
  J 376.8 N s (cleat_10, 20 m/s) and 733.0 N s (cleat_15, 10 m/s); D 1858 N (washboard,
  10 m/s). Its peaks reproduce C6a's table (24.0, 26.6 kN; washboard's minimum 1.16 kN).
- **The verdict**, per case and query, from the 240 and 480 Hz runs:
  - *a sampling artefact*: J (or D) at 480 Hz within 30 % of the reference's, and within
    10 % of its 240 Hz value, while the peak (or, for washboard, the minimum's distance from
    static) has grown by at least 30 % from 60 Hz;
  - *too stiff*: J (or D) at 480 Hz more than 30 % over the reference's, or still rising by
    more than 10 % from 240 to 480 Hz;
  - otherwise *unsettled*, reported as it is.
  C6a's rule and its verdict are unchanged.
- **118's prediction**: a sampling artefact in all six (three cases, two queries). The per-step
  mean already integrates our contact's force over the step, and R5's cam spreads it over
  the footprint, so a finer step should resolve the same impulse into a narrower, higher
  peak.
- If the verdict is a sampling artefact, which physics rate scensim defaults to is a
  separate decision (the frame's cost doubles with each doubling), not part of C6a3.
- **Approved by 133** (2026-11-23, as written).

#### C6a3's result (2026-11-23, 118)

siw 38ada7b, aib ff5e72b; GPU0 with nothing else on it; every start within the check; 60-240 Hz
from C6a2's runs; logs on the NAS, "2026-11-23 086 C6a3 impulse (118)". J in N s, D in N,
peak (washboard: the minimum's distance from static) in kN; raycast, then sweep:

| | ref | 60 Hz | 120 Hz | 240 Hz | 480 Hz | verdict |
|---|---|---|---|---|---|---|
| cleat_10 20 m/s, J | 376.8 | 391 / 404 | 395 / 399 | 403 / 404 | 402 / 404 | artefact / artefact |
| peak | 24.0 | 17.1 / 27.7 | 28.9 / 39.5 | 48.9 / 43.6 | 53.6 / 55.0 | |
| cleat_15 10 m/s, J | 733.0 | 796 / 815 | 805 / 815 | 839 / 853 | 882 / 887 | artefact / artefact |
| peak | 26.6 | 28.5 / 30.7 | 31.3 / 40.6 | 52.7 / 49.7 | 58.2 / 58.0 | |
| washboard 10 m/s, D | 1858 | 1976 / 1974 | 2152 / 2157 | 2206 / 2208 | 2223 / 2225 | unsettled / unsettled |
| swing | 3.31 | 3.38 / 3.35 | 3.68 / 3.74 | 3.78 / 3.81 | 3.87 / 3.86 | |

- **The cleats: a sampling artefact**, as predicted. The impulse stays put while the peak
  triples (cleat_10 at 20 m/s: J within 4 % from 60 to 480 Hz, 7 % over the reference; the
  peak 17 to 55 kN). cleat_15's J creeps up 5 % from 240 to 480 Hz, inside the rule's 10 %, and
  ends 20 % over the reference. So C6a's peak rule, judged on a step's mean at any one rate,
  measures the rate as much as the contact; the impulse is the rate-free measure. The 480 Hz
  peak, still growing, says the contact's force is narrower than the reference's. cleat_15 is
  an artefact at the rule's edge, not a clean one: its J ends 20 % over the reference and
  still rose 5 % from 240 to 480 Hz (133).
- **Washboard: unsettled** by the rule, not as predicted. D converges (0.8 % from 240 to
  480 Hz) and ends 20 % over the reference, but the swing grew 14 % from 60 Hz, under the
  rule's 30 %: there was little peak growth for an artefact to explain. Read plainly, the
  contact swings about 20 % harder than the quarter car on washboard at every rate, within
  C6a's band. 118's prediction (an artefact) missed here. That steady excess is a contact
  finding and goes to C6c beside the wheel mass (133).
- Neither is *too stiff* by the rule (no impulse more than 30 % over the reference, none
  still rising 10 %). C6b's rock checks may rest on this contact, judged by impulse or at a
  rate stated with the check; which rate scensim defaults to is a separate decision.

#### C6b's rocks (spec written 2026-11-23, before any run; for 133's approval)

R4's rocks on a record course: placed from the record's strips, R4's four fixtures driven as
C6a drives, and the budget on Haruna. Checks by impulse against a reference wherever one
exists (C6a3); a check on a peak names its physics rate; budget lines at 60 Hz, today's
default, which is what users run (133).

- **The code** (siw, a branch off main 38ada7b, with its unit tests):
  - *Placement from the record.* R4's zones are the parametric section's (carriageway,
    shoulder, ditch). On a corridor with stations a rock's zone is the record's strip at its
    station: carriageway, shoulder, runoff (`runoff_len`), ditch (foreslope, bottom and
    backslope to the section's extent); `rocks.Zones` gains a `runoff` cover. The
    carriageway's cover is 0 unless the course gives one.
  - *Fixed rocks* for a fixture: `rocks: {at: [[u, v, height, embed, loose], ...]}` (height
    above the surface m, the share of the rock below it, loose or static), each a seeded R4
    hull of Zingg's axes, the hull's long axis along the road.
  - *`fixture_drive`* drives C6a's way with the rig's skid plate (`ground_clearance`, 0.138 m,
    as the world server's ego has it) and logs per PhysX step, beside C6a's columns,
    PhysX's jounce per wheel and each fixed rock's pose.
- **C6a's drives had no skid plate** (found writing this spec): `fixture_drive` made the
  vehicle without the rig's `ground_clearance`, and the world server's ego has one at
  0.138 m. cleat_15 stands 15 cm across the whole carriageway, over that clearance, and a
  compressed suspension lowers the plate further, so in the world server the plate may strike
  cleats C6a judged without it. C6b's first run repeats C6a's cleat_10 and cleat_15 cases at
  60 Hz with the plate and reports whether it strikes and how J and the body rise change;
  C6a's verdicts stand as measured.
- **The fixture course, `fixture_c6b`**: C6a's straight road, level, with a record section
  whose shoulder, runoff (1 m) and ditch are real strips, and R4's fixtures (`spikes/
  rock_fixtures.py`) on the left lane:

  | s (m) | fixture | rock | speed |
  |---|---|---|---|
  | 100 | embedded_15 | static, 15 cm proud, 30 cm long, under the left wheels | 40 km/h |
  | 200 | loose_15 | loose, the same size (about 11 kg) | 40 km/h |
  | 300 | loose_8 | loose, 8 cm, under the left tyres' outer edge | 40 km/h |
  | 400 | boulder_35 | static, 35 cm, between the wheel tracks | 10 km/h |

  Elsewhere, rocks placed from the record at R4's assumed cover (shoulder 1 %, runoff 1 %,
  ditch 3 %, carriageway 0). Both wheel queries, as in C6a.
- **The checks on the fixture:**
  - *embedded_15*: the front-left wheel's excess impulse J (C6a3's measure, the hub from 1 m
    before the rock to 1 m past it) within 30 % of R0's quarter car at 4 kHz over the rock's
    top along the left track (the hull's own profile, the tyre's envelope); the wheel rises
    at least 5 cm and the body pitches at least 0.3 deg (each against its 10 m before); no
    step at PhysX's rigid limit (any wheel's jounce within 1 mm of its travel), any wheel.
    The 60 Hz peak is reported beside R4's 57.5 kN, not judged.
  - *loose_15, loose_8*: the rock moves (at least 5 cm) and is not lost (its centre stays
    within 20 m and above the ground less 0.1 m); its largest speed at most the car's (R4's
    bound: no faster than the surface pushing it); no step at the rigid limit.
  - *boulder_35*: the skid plate strikes and the car high-centres: its speed under 0.5 m/s
    within 3 s of the front axle reaching the boulder, the front axle past the boulder's
    leading edge; no step at the rigid limit. The 60 Hz deceleration peak is reported.
  - *placement*: no placed rock on the carriageway; each strip's placed cover (rocks' plan
    area over the strip's area, over the course) within a factor of 2 of its k.
- **The budget on Haruna** (C5's course rebuilt with rocks from its record at the same cover,
  GPU0 with nothing else on it; `nvidia-smi` before each run in the log; 60 Hz):
  - one ego, haruna_down under Autoware as C5 ran it, three runs with rocks and three
    without, interleaved, judged on the medians (Haruna's pose error is bimodal, C5): the
    world server's median frame p50 with rocks at most 5 ms over without, and the median p95
    under 45 ms;
  - two cars without Autoware or sensors (`fixture_cost`'s drive), a simplification accepted
    by 133, on the rebuilt course: frame p50 at most 50 ms (real time). Reported beside it: the
    same with one car, and our contact. The budget with two Autoware egos is open (below).
- **118's predictions:** every fixture check holds under both queries (R4's slice saw the
  same behaviours on a flat base); the placement check holds; the one-ego budget holds (the
  rocks are off the carriageway and few wake), the p95 bound on an idle GPU too; two cars keep
  real time.
- **Approved by 133** (2026-11-23, with the plate's repeat first, 3 + 3 Haruna runs judged on
  medians, and the two cars named as a simplification).

#### C6b's run (a): the cleats with the plate, no rocks (2026-11-23, 118)

Writing the plate in, two faults turned up (issues 119 and 120, 133's numbers): the detail
collides with the chassis and the plate only when the corridor has rocks, and on a
`section_in_base` corridor its tiles, render mesh and rock rests leave out the section, 2-7 cm
above the true road. So the plate's repeat became two runs (133): (a) fixture_c6a as built, no
rocks, no tiles; (b) with the record's rock cover, after both fixes.

Run (a) (siw 3ac4e4c, aib ff5e72b, 60 Hz, GPU0 with nothing else on it; NAS "2026-11-23 086
C6b run a skid plate (118)"), raycast / sweep, against C6a2's 60 Hz runs without a plate:

| case | plate's lowest clearance (mm; 137 before) | largest deceleration (m/s^2) | J change | body rise change (cm) |
|---|---|---|---|---|
| cleat_10, 10 m/s | 38 / 39 | 8.1 / 8.3 | -3.9 % / 0.0 % | -0.34 / -0.01 |
| cleat_10, 20 m/s | 54 / 44 | 10.8 / 10.4 | 0.0 % / -1.9 % | 0.00 / -0.36 |
| cleat_15, 10 m/s | **-5 / +0.5** | 19.7 / 23.9 | 0.0 % / +8.2 % | -0.03 / +1.64 |

- The plate meets nothing but the base road here, as issue 119 says: over cleat_15 its bottom
  goes 5 mm into the cleat (raycast) and 0.5 mm over it (sweep), and passes. With a collider it
  would strike. cleat_10 leaves it 38-54 mm.
- J and body rise are as without the plate (C6a2's run of the same code but the plate), but
  sweep's cleat_15 (+8 %, +1.6 cm), within the spread its runs show (C6a's sweep: 20.3 cm).
- The deceleration is the wheels' impact, with no plate contact in this run; it is the
  baseline (b) is set against. No step at PhysX's rigid limit.

#### C6b: issues 119 and 120 fixed, the replay, the cost and run (b) (2026-11-23, 118)

siw `086-c6b` 3381a36 (5940bc2 the fixes), aib ff5e72b, fixture_c6a, 60 Hz, GPU0; NAS
"2026-11-23 086 C6b issues 119 120 fix runs (118)".

- **The replay** of run (a) with the detail's colliders built, no rocks, raycast / sweep
  against run (a): cleat_10 at 10 m/s J -0.0 % / -5.0 %, at 20 m/s -2.8 % / -0.1 %; body rise
  within 0.3 cm. Two runs of the same code differ by up to 8 % (C6a2 against run (a)), and the
  runs are not bit-identical between processes (loads part in the run-up, before any
  fixture), so the spread is known from two or three runs a case. PhysX's jounce over the
  cleats matches run (a) under both queries: no sign of the wheels' query meeting the tiles
  (the road counted twice would compress it at the cleat). cleat_15: the plate now stops at
  +1.3 mm (raycast; -5 mm before, through the cleat) and +1.9 mm (sweep), J -11.0 % / -1.1 %,
  body rise -2.5 / -0.2 cm, the deceleration peak 16.3 / 21.5 m/s^2 (19.7 / 23.9 before): the
  plate strikes and takes load off the wheel.
- **Issue 119's cost** (medians of three a side, interleaved; frame ms):

  | query, cars | p50 with / without the colliders | p95 with / without |
  |---|---|---|
  | raycast, 1 | 6.41 / 6.64 | 21.0 / 8.6 |
  | raycast, 2 | 11.27 / 12.05 | 27.3 / 15.0 |
  | raycast, 4 | 20.57 / 20.35 | 35.3 / 24.0 |
  | sweep, 1 | 6.72 / 6.48 | 21.3 / 8.3 |
  | sweep, 2 | 12.35 / 12.34 | 28.1 / 16.3 |
  | sweep, 4 | 20.69 / 20.76 | 34.4 / 126.1 |

  The p50 does not move (-0.8 to +0.25 ms, inside the runs' spread). The p95 rises by about
  12 ms: the frames in which a tile collider is made, PhysX taking in a new mesh (the tile's
  own frame-end work is 0.06-0.09 ms p50, its p95 14 ms with two cars or more; 10-14 tiles
  held). Not explained: sweep with four cars and no colliders had a p95 of 122-142 ms in all
  three runs, against 34 with them. Rep 1's runs from 17:08 to 17:27 shared GPU0 with another
  session's job, and every run to 17:40 shared the host with row (a)'s training on GPU1; the
  medians and reps 2 and 3 alone agree. C6b's budget judges this, on Haruna.
- **Run (b)**, the record's rock cover on fixture_c6a (shoulder 1 %, run-off 1 %, ditch 3 %,
  carriageway 0): the same as the replay to the bit, both queries. The rocks lie on the
  shoulders and in the ditches (offline, 76 placed between s 180 and 320, 37 on the shoulders,
  39 in the ditches), off the car's path, and the tiles they rest on were already there: what
  (b) was to show (the plate against a cleat that collides) the replay shows.
- 133's notes: the p95 cost is the fix's known cost, judged by C6b's Haruna budget (pre-cooked
  or asynchronously built tiles a possible later step); sweep with four cars and no colliders
  at 122-142 ms p95 is an open observation; and C6b's `fixture_drive` logs the rocks in the
  stage and the rocks awake, so that rocks present is measured, not inferred from the
  placement.

#### C6b's runs: the reference and what is logged (2026-11-23, before the runs)

- **fixture_c6b** (`courses/fixture_c6b.yaml`, built by siw 67af532): 520 m, the four fixtures
  as fixed rocks (siw 67af532's `rocks: {at: ...}`), each a seeded hull scaled to stand proud
  as asked: embedded_15 18.1 kg (16.7 cm tall, 10 % sunk), loose_15 13.2 kg, loose_8 2.0 kg,
  boulder_35 327 kg (43.7 cm tall, 20 % sunk; R4's was 154 kg); the record's strips with a 1 m
  run-off each side.
- **The reference** for embedded_15, computed before the runs: R0's quarter car at 4 kHz (C6a's
  constants) at 11.11 m/s over that rock's top along the track over its centre (14.7 cm
  proud, 34.4 cm long there), the tyre's envelope: **J 653.9 N s**, peak 25.5 kN, the wheel
  rising 16.4 cm, airborne 0.25 s. `course.rock_check` judges J against it; R4's live peak
  (57.5 kN, its rock 16 cm and differently shaped) is reported beside ours.
- **Logged** per PhysX step beside C6a's columns: PhysX's jounce per wheel, the plate's
  clearance, the longitudinal acceleration, the front-left wheel centre's height, and the
  rocks in the data, in the stage and awake, and the case's own rock's pose and speed (133's
  note: the rocks there measured, not inferred).

#### C6b's fixture results (2026-11-23, 118)

siw `086-c6b` 975871e (8ff67e1 for rock_check's output), aib ff5e72b, fixture_c6b, 60 Hz, the
plate and the detail's colliders on, GPU0 with nothing else on it, every start within the
check; NAS "2026-11-23 086 C6b rock fixtures (118)". Raycast / sweep:

| fixture | measured | check |
|---|---|---|
| embedded_15, 40 km/h | J 303 / 305 N s (reference 653.9), peak 15.1 / 13.9 kN (R4 57.5), wheel rise 9.5 / 9.7 cm, pitch 0.41 / 0.42 deg, no rigid-limit step | **J fails** (-54 %); the rest pass |
| loose_15, 40 km/h | moved 1.5 / 1.5 cm, its largest speed 0.01 / 0.007 m/s, woken | **moves fails**; not lost, no faster than the car, no rigid-limit step pass |
| loose_8, 40 km/h | moved 0.9 / 1.4 cm (2.1 at most), largest speed 0.02 / 1.9 m/s, woken | **moves fails**; the rest pass |
| boulder_35, 10 km/h | stopped 0.35 s after the plate's front reached it, the front axle past its face (399.94 / 399.97 m, face 399.55), deceleration peak 169 m/s^2 at 60 Hz (R4 22), no rigid-limit step | passes |

The rocks were there, measured (133): 66 to 253 in the data, 35 to 49 in the stage, the case's
loose rock awake when the wheel reached it.

- **embedded_15 fails the J check as written** (133): it rides up as R4's did (9.5 cm against
  its 11.1), but carries half the reference's impulse. A likely cause, not tested: the reference is a 1-D profile, the rock as
  wide as the tyre's whole contact, while this rock (about 23 cm across, the tyre 23.5) meets
  only part of R5's cams across the width. Untested; to be tested later with a reference that
  covers the rock's width share of the tyre, its prediction first (133). The check is not
  changed.
- **The loose rocks did not move** (issue 122; the Haruna budget waits for it): the wheel climbed loose_15 (its load 12.7 kN) and left it
  where it lay, 1.5 cm on; R4's slice shoved the same rock 0.2-0.5 m on and 0.9-1.0 m aside, on
  a flat base without collision tiles. Not explained: the rock wakes, rests 7 mm lower on the
  tiles, and takes the push (`RockStream.push`) only as a rigid body; why its speed stays near
  zero is open.
- **boulder_35** high-centres the car. Its 169 m/s^2 is one 60 Hz sample of a stop against a
  327 kg static hull (R4's boulder was 154 kg); the car did not stand still 3 s at once after
  it (`stuck_at_s` none), so the case ran its 60 s.
- **Placement fails as written:** none on the carriageway, but the placed cover is 0.227 % on
  the shoulders (138 rocks) and 0.205 % on the run-off (168), against k = 1 %, outside a factor
  of 2. The written expectation was wrong: k is Golombek and Rapp's cover by rocks of every
  size, and placement starts at 9 cm (smaller is gravel, a surface class), so the placed share
  is the truncation factor exp(-q 0.09), about 0.22, of k (q = 1.79 + 0.152 / k = 17.0). **The
  check amended after the results** (133): placed cover within a factor of 2 of 0.22 k. It
  passes (0.227 % and 0.205 % against 0.217 %). **The ditch is untested**: fixture_c6b has
  none, so its 3 % cover placed nothing.

#### C6b's fixtures rerun after issue 123 (2026-11-23, predictions before the run)

Issue 123 found that every C6b fixture run above was made in `fixture_drive`'s faulty order. The
world's USD was added before play and `roadBase`'s members were set after it, so the loose rocks
also touched the base road. The world server never had that contact. siw 2ef3001 sets the members
before play in `fixture_drive` (133's ruling) and adds the load-time self-check (an error when a
rock touches `roadBase` within its first second awake, listed in `cases.json`). The rerun uses
the same fixture set, both queries and `rock_check` with the placement, and is reported against
the table above.

- **118's predictions:**
  - The self-check finds no base contact in either query.
  - loose_15 moves about 6.5 cm in raycast and 1.6 cm in sweep, as in issue 123's runs in the
    server's order (within 1 cm). Its largest speed is about 1.4 m/s. The check's moves item
    passes in raycast and fails in sweep.
  - loose_8 moves more than before (0.9 / 1.4 cm) in both queries. Its moves item passes in
    raycast and fails in sweep, as loose_15's.
  - embedded_15 and boulder_35 are unchanged within 5 % in every measure, verdicts as before
    (J fails, the boulder passes). Both are fixed rocks, static in `rockTiles`, and the wheel's
    load is our contact's, so the base filter does not reach them.
  - Placement is unchanged: it is offline and does not depend on the order.


#### C6b's fixtures rerun after issue 123: results (2026-11-23, 118)

siw 2ef3001, aib ff5e72b, fixture_c6b (unchanged), 60 Hz, the plate and the detail's colliders
on, GPU0 with nothing else on it, every start within the check; NAS "2026-11-23 086 C6b rock
fixtures after issue 123 (118)". Raycast / sweep, with the earlier faulty-order run in brackets:

| fixture | measured | check |
|---|---|---|
| embedded_15, 40 km/h | J 303.1 / 305.0 N s (303 / 305), peak 15.1 / 13.9 kN (15.1 / 13.9), wheel rise 9.5 / 9.7 cm, pitch 0.41 / 0.42 deg, no rigid-limit step | **J fails** as before; the rest pass |
| loose_15, 40 km/h | moved **1.67 m** / 2.5 cm (1.5 / 1.5 cm), largest speed 5.5 / 1.3 m/s (0.01 / 0.007) | raycast **passes**; sweep: **moves fails**, the rest pass |
| loose_8, 40 km/h | moved 1.1 / 5.0 cm (0.9 / 1.4 cm), largest speed 0.44 / 1.1 m/s (0.02 / 1.9) | **moves fails** in both (sweep just under 5 cm); the rest pass |
| boulder_35, 10 km/h | stopped 0.35 s after the plate's front reached it, the front axle at 399.94 / 399.96 m (face 399.55), deceleration peak 169 m/s^2 | passes, as before |
| placement | unchanged (0.227 % shoulder, 0.205 % run-off) | fails as written, passes as amended, as before |

The self-check found no rock on the base road in either query (`base_contacts` empty, no error
logged). Each load logged 1 "only in one collision group" warning.

Against the predictions:

- No base contact: holds.
- loose_15 in raycast: **fails.** It moved 1.67 m at up to 5.5 m/s, not about 6.5 cm. The front
  wheel climbed it at s = 200 m and moved it 9 cm aside. The rear wheel met it 2.9 m later and
  threw it, 0.73 m on and 1.5 m aside by the end of the case. That is the order of R4's slice
  (0.2 to 0.5 m on, 0.9 to 1.0 m aside).
- loose_15 in sweep: holds (2.5 cm against 1.6, within 1 cm; speed 1.3 m/s).
- loose_15's moves item, passing in raycast and failing in sweep: holds.
- loose_8 moving more than before in both queries: holds. Its moves item passing in raycast:
  **fails** (1.1 cm).
- embedded_15, boulder_35 and placement unchanged: holds.

Open, not tested: issue 123's single-case runs moved loose_15 6.5 cm in raycast, against 1.67 m
here. Those runs ran with `--trace-push`, which applies PhysX's contact report to the rock's prim
while it is being simulated and wraps `rocks.limit`. In this run every rock has the report from
its creation, and nothing is wrapped. Whether the trace changed the rock's motion is not tested.

**Afterwards (2026-11-23, issue 123's trace hypothesis):** the trace changed nothing. loose_15
alone moved 6.6 cm with `--trace-push` and without it. The 6.6 cm against 1.67 m difference is
the case run alone against the whole set, which is unexplained and open. A single raycast run
does not fix this fixture's outcome. Sweep's small travel is issue 125, because a study config
(`isaac_verge`) uses sweep. Issue 122 is closed (133).


Order: C1, C2 and C3 make the shared data; C4 and C5 are its first consumers, C5 after C3.
C6 follows C5 (rocks and wheel hop on the record's road). C7 can start after C2 on 0.9.16,
and on 1.0 after 083 step 5. C8 runs beside the others. C9 comes after C5 and C6. 069 E1 and E2 (Track B, unassigned) can start once
C3 has written Haruna's record. About 4-5 weeks of work to C5, which gives one road from the
record to Isaac, Autoware's maps and the planner.

### Open

- **The budget with two Autoware egos on Haruna** (C6b's two-ego line, which C6b measures with
  two cars without Autoware): when a two-ego Haruna scenario exists. Not built for C6b (133).

### Decisions (accepted by 133, 2026-11-20)

- **The class table in `scensim_world_protocol`** (C2): the alternative is to keep it in the
  Isaac world server and have the CARLA one read a copy. Decided: move it, one table.
- **069 E1, E2, E4 are Track B's** (the planner's side), as the record is the only thing they
  share: Track B, unassigned (085 has no active owner).
- **Dataset revisions** for Haruna and Tsukuba after C3 and C5: the user's to publish.
