# 192: a soil world's cut road is reported as the static world

**Status:** fixed in code and tests (siw 03876248; 241, 2026-11-26; numbered by 133). Open: the
live soil run (plan step 4), when a GPU is free.
**Severity:** medium. No verdict has changed yet. Under issue 189's default contact judge, the
ego's contact with its own road in a soil world passes only because the static floor (10 N*s)
sits above the 0.0 measured so far. An ego that bottoms out on that road (a dip, a hard landing)
would fail a run as UndeclaredContact with the static world. **Found:** 2026-11-26, 241, issue
176's step 1.

## What happens

A soil zone with its own ground (`ground_z`) needs the world's road cut out from under it
(roadmap 047 S3). `soil_tiles.cut_stage` cuts the zone's box out of the world's ground meshes.
PhysX does not re-cook an edited mesh, so the cut collision is a new invisible mesh under the
zone's `cut` scope, `/World/soil/<zone>/cut/m<i>`, and the original mesh's collision is turned
off. The world's contact filter (`IsaacWorld._is_ground`) treats as ground only:
- the world's `ground_paths`;
- the flat plane;
- the road detail's collision tiles (`/World/RoadCollision`).

The cut copy is none of them. So the ego, on its own road outside the soil box, is in contact
with "the static world" from its spawn, in every soil run. The zone's other colliders, under
`/World/soil/<zone>/`, are the same:
- `flat`, the box other bodies stand on;
- the wheel `plates`.

The render meshes have no collision. That is also where every tracked NPC's "soil" contact in 189's table comes
from (`flat`, `cut`, 111 to 1426 N*s). Those are not judged.

Seen in 241's kept runs (189's table, 20 runs): `/World/soil/<zone>/cut/m0`, static, first at
SSv2 frame 2, about one count a frame, max impulse 0.0.

## Why 0.0 (not settled)

The wheels hold the body up, so the pair is likely the chassis or the skid plate within the
contact offset of the copied mesh's faces, or of the kerb and verge faces it keeps beside the
road. That is a pair with contact points but no solver impulse. Reading the code did not settle it.

## The plan (for 133, before any code)

1. *The zones' own ground is ground.* Everything under `soil_tiles.ROOT` (`/World/soil`) is
   the soil zones' ground: the cut copies of the world's road, the flat box and the wheel
   plates. Nothing there is something a scenario can hit. `_is_ground` takes `/World/soil` as
   ground whenever a soil zone is built (`_make_tiles`), and the ground cache is cleared when
   zones are built or removed.
2. *The test, without Isaac.* `_collect_contacts`' filter, from PhysX's report headers to the
   `(reporter, other, path, impulse)` rows, moves into a pure function, and the method calls it.
   Tests with stub headers:
   - an ego touching `/World/soil/<zone>/cut/m0` at 0.0, and at 500 N*s, gives no row (the at-rest
     case and a bottoming-out);
   - the same ego touching `/World/RoadRocks/r1` gives one, its impulse summed as now;
   - a world without soil zones reports a prim under `/World/soil` as before.
   The current filter's rows are kept on every other input: ground paths, the plane, the detail
   tiles, two reporters touching.
3. *The 0.0, logged once.* For a run's first contact under `/World/soil` (now dropped as
   ground), the world server logs its colliders (the header's `collider0`/`collider1`: the
   ego's cube or plate, and the mesh) and the smallest separation among its points, once. It
   says which pair it was, and the line stays.
4. *The live check, when a GPU is free without displacing anyone.* One soil run on 241, and
   its `contacts/` must have no `/World/soil/...` entry:
   - `isaac_soil`'s town01_soil, one of the 20 in 189's table;
   - at a scensim main with the fix, gated.
   The once-logged line names the 0.0's pair.

**Predictions, before any code:**
- The new tests fail on today's filter (the cut copy gives a row) and pass with the fix. The
  other cases' rows are unchanged.
- `just gate` passes, with the Isaac lane run (942, plus the new tests).
- The live run's `contacts/` lists no `/World/soil/...` prim. Its other contacts (none, on
  town01_soil's route) are unchanged. The logged pair is the ego's chassis cube or plate against
  a kerb or verge face of the cut copy, with a separation within the contact offset (a few cm).
  This last part is my least sure prediction.

## 133's check on raised soil features (2026-11-26, before any code)

133 asked whether a soil zone could have a raised feature (a ridge between ruts, say) that a
body could strike hard. If so, it would now count as ground, and a high floor would fit it
better than a blanket exclusion. None can be struck. A soil zone's colliders are three
(`soil_tiles`):
- the `flat` box, level at the zone's `ground_z`, which other bodies stand on;
- the wheel `plates`: a tyre's footprint each, under each ego wheel, fitted to the ruts there;
- the `cut` copies of the world's road, which were ground before the cut.

The ruts and ridges live only in the render meshes, which have no collision. So everything under
`/World/soil` is ground, and no floor is needed.

## The fix (241, 2026-11-26)

siw 03876248, on siw main a1ae4b4c:
- `contacts.py` (new, pure Python): `rows` is `_collect_contacts`' filter, which the method now
  calls. `SOIL_ROOT` is `/World/soil`.
- `IsaacWorld._make_tiles` adds `SOIL_ROOT` to the world's ground and clears the ground cache.
- The first soil-ground pair of a load is logged once, with its colliders and smallest
  separation.
- `test/test_issue_192.py`, 5 tests on stub headers.

siw's own check, in a fresh recursive clone at 03876248:
- system Python (`just check`: the tests, then pyflakes): "Ran 534 tests", OK (skipped=47);
- Isaac's Python: "Ran 535 tests", OK (skipped=19). That is 530 at a736c0b, plus the 5 new.

The first prediction (the tests fail on today's filter and pass with the fix) is shown by the
test that keeps today's ground: without a soil zone's root, the cut road gives its row. The live
check (plan step 4) waits for a GPU.

**The gate:** `gate ok dad1a526f87175d1e21b28454da9c0a0e67aef6d tree 9af5d8bc on
newslab-server-241 2026-11-26T16:16:33+08:00: build test check clean; Isaac lane ran (947
tests); colcon-cargo-ros2 0.5.5; rustfmt 1.10.0-nightly (fd7ed57dfd 2026-08-29); carried
ISAAC_ROOT`. Held: 947 is 942 plus the 5 new tests. Rebased onto 7b7abfe6 (docs only) before
landing.

## The live check (241, 2026-11-26, 20:33 to 20:38)

**Setup.**
- 241's GPU1, **shared with another user's training job** (thsxw's, steady at 10258 MiB).
- GPU1's free memory went from 21861 MiB to 14273 MiB at its lowest. A guard stopped our run
  below 4096 MiB free; it never fired.
- The build was scensim main 6690f884619bc89fb122c838e48ebe294bd0e4c7, with siw 03876248, built
  clean.
- The project was a copy of `isaac_soil`, with its own lock and assets at the lock's
  revisions. The run was town01_soil, alone.
- The run directory is 241's
  `swb-logs/soil192/runs/2026-11-26T20-35-41_town01_soil_r0`.

**Result:** the run passed, and so did `physical_verdict` ("no unexpected contact").

**The predictions:**
- **Held:** `contacts/` lists no `/World/soil/...` prim. Its one episode record is
  `complete: true`, with `contacts: []` and `npc_contacts: []`, as predicted (none on this
  route).
- **Failed:** the logged pair. The world server logged it once:
  ```
  issue 192: /World/entities/e2 touches the soil zones' ground /World/soil/dirt_road/cut/m0
  (dropped as ground): colliders /World/entities/e2/body and /World/soil/dirt_road/cut/m0,
  12 point(s), smallest separation 0.4984 m
  ```
  `e2` is the NPC `lead` (a tracked box, 4.5 x 2.1 x 1.8 m, its base at the road), spawned
  0.27 s before. It is not the ego's chassis cube or plate. The pair was the lead's box
  against the dirt zone's cut road, not a kerb or verge face. The separation is 0.50 m, not
  within a few cm. The ego reported no soil contact at all.

**Unexplained:** a reported pair whose smallest separation is half a metre. Two readings are
possible:
- PhysX reports contact points out to the sum of the two shapes' contact offsets, and the
  tracked body's offset may be that large;
- the box sits on the cut copy's sunken faces inside the zone, which the cut lowered under the
  soil grid.

Neither was measured. It needs no change: the row is ground, as the fix intends, and the
lead's body went down 0.023 m at most on the soil ("off the soil" line). Step 4 is done.
