# 192: a soil world's cut road is reported as the static world

**Status:** open; plan written (241, 2026-11-26; numbered by 133), before any code.
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
