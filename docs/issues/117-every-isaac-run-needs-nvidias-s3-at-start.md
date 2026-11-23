# 117: every Isaac run needs NVIDIA's S3 at start

**Status:** fixed, B (aib e9fea7f, scensim_isaac_world 9ad8b98, scensim_batch's smoke script). **Severity:** medium: a
run on a host whose network is slow or down fails before its first step, and every Isaac run
we have takes this path. **Found:** 2026-11-23, scensim 241, in issue 108's fix check.

## What happened

One of issue 108's fix-check runs (`aib.steptest --only limit_brake`, ABS at mu 0.2) ended 30 s
after start, before it built the car:

```
  File ".../aib/steptest.py", line 415, in main
    world.scene.add_default_ground_plane()
  File ".../isaacsim/core/api/scenes/scene.py", line 277, in add_default_ground_plane
    assets_root_path = get_assets_root_path()
  File ".../isaacsim/storage/native/nucleus.py", line 662, in get_assets_root_path
    raise RuntimeError(f"Could not find assets root folder: {default_asset_root}")
RuntimeError: Could not find assets root folder:
    https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.2
```

The same run passed when run again. Log: `~/nas/home/aeon/issue117/abs_mu0.2.failed-assets.log`.

## Why

Isaac Sim 6.2's `Scene.add_default_ground_plane()` (isaacsim.core.api, `scenes/scene.py`) does
three things:

1. `get_assets_root_path()` (isaacsim.storage.native, `nucleus.py`) reads
   `/persistent/isaac/asset_root/default`, which the extension sets to NVIDIA's S3 bucket for
   6.2. It checks that the bucket holds an asset tree, with a 10 s timeout
   (`/persistent/isaac/asset_root/timeout`) and 3 attempts, and raises when it does not.
2. It references `<root>/Isaac/Environments/Grid/default_environment.usd` at the given prim
   path. The file and its three textures come over HTTPS.
3. It binds a new physics material to the plane: static and dynamic friction 0.5,
   restitution 0.8 (`/World/Physics_Materials/physics_material`).

Nothing in our setup sets the asset root, so every run goes to S3. There are 9 callers:

- the Isaac world server (`scensim_isaac_world/world.py`, at start, as `/World/defaultGroundPlane`);
- aib's `runner.py` and `steptest.py`, when no world is given (vehicle_check, the step tests);
- `scensim_batch/scripts/smoke_physx_vehicle.py`;
- five spikes in `scensim_isaac_world/spikes/`: domains, smoke, cost, lockstep, kinematic_contacts.

### What the default environment holds

From the file itself (6.2's, 18.5 kB, kept at `~/nas/home/aeon/issue117/default_environment.usd`):

| prim (under the prim path given) | what it is |
|---|---|
| `GroundPlane/CollisionPlane` | a `UsdGeom.Plane` (axis Z) with `PhysicsCollisionAPI`: the collider |
| `Environment/Geometry` | the visible mesh, bound to `Looks/theGrid` |
| `Looks/theGrid` | OmniPBR with three textures from the bucket (`Wireframe_blue.png`, `WireframeBlur_*`), emissive |
| `SphereLight` | a sphere light, intensity 100000, radius 0.25, 2.5 m above the origin |

### What reads those prims

Checked in scensim 60ca020b's tree:

- **The tyres do not.** aib's tyre friction tables have no ground materials
  (`CreateGroundMaterialsRel()`, empty `frictionValues`), so every wheel reads the table's
  default on any ground. The plane's 0.5 never reaches a tyre.
- **Other bodies do.** Anything else touching the plane uses the material: friction 0.5,
  restitution 0.8. That covers a chassis or a skid plate grounding, and a dynamic prop or
  rock on a flat world.
- **The world server reads the path.** It reads `/World/defaultGroundPlane` by path only: it
  deactivates the plane when a world is loaded, reactivates it without one, and lists it as
  ground for contacts. It reads no child prim.
- **The light matters in two places:**
  - The world server decides whether to add its own sun and sky from the loaded world's
    lights only (`ENVIRONMENT`). So on a flat world it has its sun and sky *and* the
    sphere light.
  - aib's `runner.ensure_light` adds a sun and sky only to a stage with no light. On a flat
    world it finds the sphere light and adds nothing, so a camera on a flat world away from
    the origin sees a point light 2.5 m above the origin and nothing else.
- **The lidar does not care.** aib.intensity classes a hit by its prim's
  `semantics:labels:wikidata_qcode`, and the default environment's prims have none, so the
  ground reads as unlabelled either way.

## The fixes

### A: a local copy of the asset root

Mirror the four files (the environment and its three textures) under a local directory at
the bucket's layout, and pass `--/persistent/isaac/asset_root/default=<dir>` to every Isaac
start. For the world server that goes through `ISAAC_KIT_ARGS`; aib's runner and steptest,
the batch smoke and the spikes would each need it too.

- Same scene as today, prim for prim: no behaviour or picture changes.
- Still an NVIDIA path layout per Isaac version: the mirror is redone with each Isaac
  upgrade, and `get_assets_root_path`'s check of what counts as an asset tree must accept it.
- A setting that must reach every entry point: one that misses it still goes to S3, silently.
- The asset root is process-wide: anything else that asks for it would read the mirror, and
  fail where the mirror lacks a file.

### B: our own plane and light (133's lean)

One aib function, used by all 9 callers (the world server through its deps), that builds the
same thing locally:
- at the same prim path, a `UsdGeom.Plane` collider (axis Z) and a plain visible mesh;
- the same physics material, friction 0.5 and 0.5, restitution 0.8, so contacts other than
  the tyres are unchanged;
- no sphere light.

- No network and no NVIDIA asset path at all, on any Isaac version.
- One place to change, and a test can check it (the collider, the material's values, the
  path).
- The picture on a flat world changes:
  - no grid texture;
  - in the world server, no sphere light beside its sun and sky;
  - in aib's runner, `ensure_light` now finds no light and adds its sun and sky, so flat-world
    cameras are lit like the rest.

  No test or result compares flat-world images, as far as the tree shows. Any measurement
  that read a flat-world camera image is named before the change.
- Nothing physical changes: the tyres never read the material, and the collider and the
  material keep their values.

## Recommendation

B. A changes nothing but leaves the dependence, and moves it to a mirror kept per Isaac
version. B removes it. The only differences it brings are in the picture on a flat world,
and the world server and runner want those anyway.

Before code: a test that fails today, run with no network (no route to the bucket) through
aib's steptest on a flat world. Then the change. Then the same test, the world server's
suite, and one vehicle_check run, before and after, compared.

## The fix (B, approved by 133 on 2026-11-23)

- **aib:** `aib.isaac.ground.add_ground_plane(stage, path, z)` builds the plane with pxr's own
  `PhysicsSchemaTools.addGroundPlane`: an infinite collision plane (axis Z) under a visible
  grey square 2 km across. A physics material carries Isaac's values (0.5, 0.5, 0.8) and is
  bound to the collider. The default path is `/World/defaultGroundPlane`. `runner` and
  `steptest` use it on a flat world.
- **scensim_isaac_world:** the world server and the five spikes use it.
- **scensim:** so does `scensim_batch/scripts/smoke_physx_vehicle.py`.
- **runner.ensure_light:** no change. It adds its sun and sky to a stage with no light, and the
  flat ground now brings none.

Tests, each failing before the change:
- aib `test_ground` and scensim_isaac_world `test_no_asset_root` scan the sources for
  `add_default_ground_plane(` and `get_assets_root_path(` calls. Before, they named
  `runner.py:217` and `steptest.py:415`, then `world.py:205` and the five spikes.
- `python -m aib.ground_check` runs under Isaac with the asset root at a port nothing answers
  (`--online` keeps Isaac's; `--isaac-default` builds Isaac's plane, the state before). It
  builds the flat world as the runner does, `ensure_light` after, and checks:
  - the plane is built;
  - a 1 m box dropped from 3 m rests at 0.5 m;
  - the bound material is (0.5, 0.5, 0.8);
  - a camera at (60, 40, 1.8) without auto exposure is not dark (mean RGB at least 25 of 255).

| ground | network | built | light added | material | box at rest | camera mean RGB | pass |
|---|---|---|---|---|---|---|---|
| Isaac's default | none | no: the RuntimeError above | | | | | no |
| Isaac's default | S3 | yes | no (the sphere light) | 0.5, 0.5, 0.8 | 0.500 m | **0.0** | no |
| aib's | none | yes | yes | 0.5, 0.5, 0.8 | 0.500 m | 226.7 | yes |

Logs: `~/nas/home/aeon/issue117/{default-offline,default-online,aib-offline}.log`.

## What changes in a picture on a flat world

Earlier camera results on a flat world are to be read with this:
- **aib's runner (`just isaac-ego` with no world, vehicle_check):** a camera away from the
  origin was black. The only light was the default environment's sphere light, 2.5 m above the
  origin (camera mean 0.0 at 72 m). It is now lit by the runner's sun and sky. The ego camera
  has auto exposure and would have read black too: nothing lit it.
- **The world server on a flat world:** it had its sun and sky plus the sphere light near the
  origin, over a grid texture. It now has its sun and sky over plain grey. Roadmap 044's walker
  line-up shots (2026-10-25, all 52 walkers on the ground plane) were taken that way. They were
  judged by eye for bodies, poses and textures, which this does not change; the ground behind
  them is now grey, with no grid.
- **No measurement in the docs reads a flat-world camera image** (searched: docs citing a
  camera with a ground plane, a flat world, or `isaac-ego`). The lidar is unchanged: the plane
  has no class label either way.
- **Physics is unchanged:** the same collider kind and contact values, and the tyres read
  neither.
