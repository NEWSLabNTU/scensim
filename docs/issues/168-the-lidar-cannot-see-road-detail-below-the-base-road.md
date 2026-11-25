# 168: on road-layer worlds the lidar cannot see road detail below the base road

**Status:** open; doc and predictions first (133, 2026-11-25), no fix yet. **Severity:** high
for any sensor result on a road-detail world: the lidar (and the camera) see no pothole, no rut
and only the upper half of the roughness. **Found:** 2026-11-25, scensim 118, 086 C6e1
(predicted from the code before the run; numbered by 133).

## What happens

The road layer (066 R3) adds the detail as its own render mesh, `road_layer.MeshStream`: per
tile within 40 m of a car, the base road plus the detail (`Detail.surface_tile`), no collision.
The world's own road (the course's `world.usdc`, `/World/env/Road`) stays drawn beneath it.
Only the detail's collision copy is hidden (`rock_layer`, `CreateVisibilityAttr(invisible)`).
So a ray meets whichever surface is higher: max(base, base + detail).

In 086 C6e1 the lidar read the cleats and the washboard (above the base) to within 0.1 mm of
the detail. Every one of its 540 returns over the 8 cm pothole at 9 m was at the base road: dz
to the base was -36.22 mm (issue 167's offset alone), and dz to the pothole's floor was
+43.78 mm.

Below the base road, and so not seen:

- potholes (all of their depth);
- ruts (their 3 cm grooves; the centre windrow above the base is seen);
- the lower half of the ISO 8608 roughness, which is zero-mean, so the lidar sees the road's
  roughness clipped at the base;
- a water bar's ditch, if one is ever below the base (bars today are above it).

C6d's Haruna had all three of the first. Its "pothole detection range: not measurable" and its
"roughness did not reach localization" were measured on a cloud that never held them.

## Options (for 133; costs predicted, not measured)

1. **Hide the world's road where the detail mesh covers it, and draw the detail to the
   sensors' range.** Set `/World/env/Road`'s visibility to invisible when a road layer loads.
   Visibility does not change collision: the detail's collision tiles are invisible and
   collide. Raise `MeshStream`'s reach to the lidar's useful range (the OS1's 170 m far range;
   haruna_down's camera and lidar need about 120 m).
   - *Predicted:* 3 to 4 times the tiles drawn (40 m to 120 m reach, the area by the square
     less the corridor's width), each about 40 ms to make, streamed as now. The tick p50 rises
     by about 1 ms at 16 km/h and more at speed. Beyond the reach the road is not drawn.
2. **Lower the world's road under the detail.** At load, move `/World/env/Road`'s render 0.15 m
   down (deeper than any pothole the generator makes, 8 cm, with a margin), so the detail
   mesh is always above it where it exists.
   - *Predicted:* no extra cost. Beyond the 40 m reach the road is seen 0.15 m low: a step at
     the reach's edge in the cloud and in the camera.
3. **Cut the detail into the base road's own mesh.** The course builder writes `world.usdc`'s
   road from the same samples with the detail in it, so no second mesh is needed.
   - *Predicted:* exact at every range with no render cost per frame. The detail is baked in, so
     a scenario's road_detail change needs a rebuilt world, and a 0.05 m grid over a 2 km road
     is a large mesh (about 6.4 million vertices for 2 km of an 8 m carriageway at 0.05 m, before any decimation).

My first recommendation was option 1, with its reach and cost measured first (C6e2's method).
It is amended below, before any code.

## What else reads the base road's render (133's check, 2026-11-25, before any code)

Option 1 hides the world's road from every renderer, not only from the lidar. Beyond
`MeshStream`'s reach nothing draws the road. The course's terrain is then what is seen there, 0.30
m below the road on a fixture course (`terrain_below`), and the world's own terrain on Haruna.
These read the render beyond 120 m:

- **The lidar itself.** The Model 3 rig gives it `range: 200.0` m (`tesla_model3.rig.yaml`'s
  profile), and the OS1 profile's far range is 170 m. Its road returns from 120 to 200 m would
  come from the terrain. NDT uses them, and the ground filter would see a drop at 120 m.
- **The ego's camera.** `camera6` is `enabled: false` in the rig, so no Autoware run so far has
  had one. Traffic light recognition names camera6 but runs fusion only by default
  (`traffic_light_fusion_only: true`). Turned on, its clipping range is 0.1 to 1000 m
  (`aib.isaac.sensors.Camera`): it would see the road end at the reach.
- **The viewport and recordings.** The world server's `--display`/`--follow` viewport (the
  demos' videos) looks along the road to the horizon. Option 1 would show the road ending 120 m
  ahead.
- **rviz** draws the topics (the clouds, the map's own cloud and lanelets), not Isaac's render.
  It sees the lidar's effect only.

So option 1 as written breaks the demos' view and the lidar's far returns. **Amended
recommendation (before any code):** option 2 with option 1's mesh. Keep the world's road
drawn, but lowered by 0.15 m under the corridor, and keep `MeshStream`'s 40 m reach, raised
only if C6e3 needs the detail further out. Then:

- within the reach, the detail is drawn exact (the base road is below it);
- beyond it, the road is drawn 0.15 m low;
- the demos see a road to the horizon, with a 0.15 m step at the reach's edge in the lidar and
  in a camera.

*Predicted cost:* none per frame, since only the base road's transform moves once at load. The
step at the reach is a known artefact, to be measured (the ground filter's split at 40 m, NDT's
NVTL). Option 3 (bake the detail in) removes the step and stays the target for published
worlds. Option 1 remains if 133 prefers no step and accepts the view's end.

## Predictions for the fix (before any code)

- C6e1 rerun: over the pothole, dz to the floor within 0.5 mm of issue 167's offset, out to the
  reach. The cleats and the washboard are unchanged.
- C6d rerun (one rough_none run): the roughness's effect on localization stays within C6d's
  noise. *Hypothesis:* NDT's 2 m voxels average a few centimetres out.

## Reach

Every lidar or camera result on a road-detail world (C5d, C6b, C6d, 158's reruns, 157). The
judged A/Bs (C6b's and C6d's rocks) compared two sides with the same blindness. Their verdicts
stand for what they compared, and their absolutes say nothing about potholes and ruts. Worlds
without `road_detail.yaml` (Town01 on Isaac, the published Haruna) have no detail mesh and are
not affected.
