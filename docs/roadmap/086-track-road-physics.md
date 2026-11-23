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
(scensim_isaac_world b5de87b, its fixture course and checks).
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

#### C5c's fixtures (spec written 2026-11-23, before they are built)

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
  | 1, 2, 3 | 5 cm | 90, 45, 30 deg | re-enters (not over 5 cm) |
  | 4 | 10 cm | 90 deg | **held** |
  | 5, 6 | 10 cm | 45, 30 deg | re-enters (face not steeper than 45 deg) |
  | 7 | 15 cm | 90 deg | **held** |
  | 8, 9 | 15 cm | 45, 30 deg | re-enters (face not steeper than 45 deg) |
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
  on 118's GPU0.
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
  failed check. C5c's check is that every case ran and is classified, and that the control
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

Order: C1, C2 and C3 make the shared data; C4 and C5 are its first consumers, C5 after C3.
C6 follows C5 (rocks and wheel hop on the record's road). C7 can start after C2 on 0.9.16,
and on 1.0 after 083 step 5. C8 runs beside the others. C9 comes after C5 and C6. 069 E1 and E2 (Track B, unassigned) can start once
C3 has written Haruna's record. About 4-5 weeks of work to C5, which gives one road from the
record to Isaac, Autoware's maps and the planner.

### Decisions (accepted by 133, 2026-11-20)

- **The class table in `scensim_world_protocol`** (C2): the alternative is to keep it in the
  Isaac world server and have the CARLA one read a copy. Decided: move it, one table.
- **069 E1, E2, E4 are Track B's** (the planner's side), as the record is the only thing they
  share: Track B, unassigned (085 has no active owner).
- **Dataset revisions** for Haruna and Tsukuba after C3 and C5: the user's to publish.
