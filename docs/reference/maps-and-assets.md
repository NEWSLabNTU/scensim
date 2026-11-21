# Maps and assets

What a map directory holds, the datasets a testbench can fetch, and CARLA's assets in USD.
How a testbench takes them: [The testbench file](project-file.md#assets).

## A map directory

One directory per map, in Autoware's map layout plus each simulator's files:

```
<map>/  lanelet2_map.osm  pointcloud_map.pcd  pointcloud_map_metadata.yaml
        map_config.yaml   map_projector_info.yaml
        carla/map_origin.yaml       (only for a map not in CARLA's frame)
        isaac/world.yaml            (Isaac Sim: the world for this map)
        surfaces.yaml               (Isaac Sim: optional, the label defaults)
        anchors.yaml                (optional: the map's anchors, by name)
        anchors.resolved.json       (made from anchors.yaml by the map's author)
```

A fetched map is read-only. What the stack writes for a map goes to the testbench's
`state/<map>/`:

| In `state/<map>/` | Written by | What |
|---|---|---|
| `traffic_lights.yaml`, `carla/traffic_lights.yaml` | CARLA's world server, the first time it loads the map (and again when the map's lanelet2 changes) | which Lanelet2 signal is which CARLA light |
| `ruts/runs/<time>.npz` | Isaac's world server, at each scenario's end | the soil's ruts |
| `surfaces.yaml`, `road_detail.yaml`, `surfaces/<name>.yaml` | you ([Road physics](road-physics.md)) | the testbench's ground for this map, used over the map's; the named maps a scenario picks |

**A map not drawn in CARLA's frame** needs `carla/map_origin.yaml`: the map-frame position
of CARLA's world origin, in metres, no rotation. CARLA's towns share CARLA's origin and need
none; a surveyed map uses grid coordinates tens of kilometres from zero.

```yaml
# <map>/carla/map_origin.yaml
x: 52600.0
y: 67800.0
z: 0.0       # optional
```

Both vehicle bridges read it. No file means an origin of zero; a file that does not parse
stops the run rather than putting every pose hundreds of metres off.

**The Isaac world file** names the world's USD stage, where its origin sits in the map
frame, and the prims a car rests on (whose contacts are not collisions):

```yaml
# <map>/isaac/world.yaml
usd: ${SCENSIM_CARLA_USD}/Town01/Town01_physics.usda
map_origin: [0.0, 0.0, 0.0]
ground_paths:
  - "/World/env/..."
```

`usd:` may name the stage through `${SCENSIM_CARLA_USD}` (the testbench's `assets/carla-usd`, set
by the stack), relative to the map directory, or absolutely. `ros2 run scensim_isaac_world
make_world <map dir> [--town <Town>] [--usd <stage>]` writes it for a CARLA town from the
USD set; it runs in Isaac's Python.

## A map's anchors

A map may name parts of its geometry for scenarios: a lane by the lanelets it runs along, so a
scenario's derived values can read its length, speed limit or heading
(`anchor.<name>.heading(s)`, scenario-description.md sections 2a and 3). The map's author
declares them in `anchors.yaml`:

```yaml
anchors: 1
lanes:
  # Town01's street where follow_to_goal starts
  west_street: {lanelets: [6583]}
  # the street, then its left turn: each lanelet follows the one before
  west_left_turn: {lanelets: [6583, 42664, 32582]}
```

and resolves them, once, into `anchors.resolved.json` beside it:

```bash
# the map's export: lanelet2, in system Python
python3 -m scensim_batch.map_export <map dir> -o export.json
# its anchors resolved: needs torch
python3 -m scensim_batch.anchors resolve <map dir> --export export.json
```

**Only a map's author runs these.** A user reads the resolved file, with ROS 2 alone: the
sampler and `scensim` read its numbers and never need lanelet2 or torch. The file records the
map's digest, and a file resolved on other map bytes is refused. A lane's length and its arc
positions are SSv2's (its Catmull-Rom spline through each lanelet's centreline), so an `s` read
from an anchor is an `s` in a LanePosition. Its heading is a table: every 0.5 m, each lanelet
join and each joint of a lanelet's spline listed twice (the tangent before and after, which
need not agree), and any interval whose linear interpolation is off by more than 1e-3 rad
halved, down to 1 cm. The file states the step, the tolerance and the error it measured
(`heading_max_error`): Town01's left turn measures 9.9e-4 rad.

The published maps dataset does not carry anchors files yet: until it does, a host that has
them keeps a copy of the dataset of its own (`datasets:` in `host.yaml`), which `scensim assets
fetch` links instead.

A testbench's `world.anchors` adds anchors of the project's own, as stated numbers; a name
both declare is refused. Conflict points, curves and regions come later (roadmap 092 K9c).

## Datasets

Public, on Hugging Face under `jerry73204`; `scensim assets list` prints them with
their sizes.

| Dataset | Holds | Licence |
|---|---|---|
| [carla-town-autoware-maps](https://huggingface.co/datasets/jerry73204/carla-town-autoware-maps) | Town01, 02, 03, 05 and 10 as Autoware maps, each with its Isaac world file; `town05_ring_110kmh/` (Town05's ring road at 110 km/h); `town01_pcd_isaac_world/` (a light Town01 world built from the point cloud, about 10 MB) | LGPL-3.0 |
| [carla-coop-scenario-maps](https://huggingface.co/datasets/jerry73204/carla-coop-scenario-maps) | the coop study's Autoware maps of Town03, 04 and 05, 0.70 GB | LGPL-3.0; Town04 CC BY 4.0 |
| [carla-0.9.16-isaac-usd](https://huggingface.co/datasets/jerry73204/carla-0.9.16-isaac-usd) | CARLA 0.9.16's content as SimReady USD, 25.5 GB: six towns, `vehicles/` (41 vehicles, `props/` 97, `walkers/` 52, indexed by `vehicles.json`, `props.json`, `walkers.json`, `vehicles.md`) | CC BY 4.0 |
| [haruna-tsukuba-courses](https://huggingface.co/datasets/jerry73204/haruna-tsukuba-courses) | the Mount Haruna mountain road and Tsukuba Circuit: Autoware maps, Isaac worlds, a scenario each; their props come from the USD set | ODbL, GSI |
| [isaac-road-physics-stages](https://huggingface.co/datasets/jerry73204/isaac-road-physics-stages) | the flat test ground with 13 surface strips and its surface map, the vehicle check's proving ground, `procedural/` (the rough road for Town01, worn ruts) | Apache-2.0 |
| [newslab-golfcart-models](https://huggingface.co/datasets/jerry73204/newslab-golfcart-models) | a golf cart for Isaac Sim: body, rig, vehicle spec, catalog entry, RViz mesh | Apache-2.0 |

A testbench takes only what it names (`take:`): Town01 of the maps is about 0.1 GB; Town01
and `vehicles/` of the USD set several GB. Each dataset is verified file by file against
its manifest when it has one.

**The CARLA towns' maps** are TUM's
[CARLA-Autoware-Bridge](https://github.com/TUMFTM/Carla-Autoware-Bridge) conversions (map
pack copyright 2024 TUM, LGPL-3.0), with repairs Autoware and SSv2 need: traffic-light type
tags, lanelet subtypes and turn directions, line types, bound directions, local
coordinates, duplicate points, joins, right-of-way elements, speed limits and walkways from
CARLA's OpenDRIVE, and each signalised approach linked to its CARLA light. CARLA calls
Town10 `Town10HD`; the map directory is `Town10`.

**CARLA's assets in USD.** Isaac renders CARLA's towns, vehicles, props and walkers from
the USD set; a scenario entity's `model3d` picks its model by CARLA blueprint id
([Tutorial 6](../tutorials/06-carla-assets-on-isaac.md)). For developers, how the set is made
from a CARLA editor build: [Isaac assets](../design/isaac-assets.md).
