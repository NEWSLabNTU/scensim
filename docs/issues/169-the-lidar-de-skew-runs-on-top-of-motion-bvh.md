# 169: aib's lidar de-skew runs on top of motion BVH's own sensor motion

**Status:** open; after 167 and 168 (133, 2026-11-25). **Severity:** none today, since motion
BVH is off in every run (issue 138), but it blocks turning motion BVH on. With it on,
localization runs about 0.108 m ahead of the car at 4.5 m/s. **Found:** 2026-11-25, scensim
118, 086 C6e2 (numbered by 133).

## What happens

086 C6e2 ran smooth haruna_down three times with motion BVH off and three times with it on
(`ISAAC_KIT_ARGS` with SimulationApp's `enable_motion_bvh` settings). Localization's error
against the truth, median above 1 m/s (`c6e2/along.py`):

| side | along the track | across | pose error p95 |
|---|---|---|---|
| off (f1, f2, f3) | +0.007 m | -0.065 to -0.067 m | 0.118 to 0.120 m |
| on (o1, o2, o3) | +0.107 to +0.109 m | -0.070 to -0.071 m | 0.188 to 0.191 m |

NVTL p05 is the same on both sides (3.119 to 3.120). Record: NAS "2026-11-25 086 C6e2 motion BVH
cost (118)".

## Why (a hypothesis)

aib's `Lidar._msg` de-skews each point along the sensor's own track (`motion_distort`, by the
point's firing time). It assumes the render saw the whole revolution from the one pose it was
rendered from, `latency` frames back. Without motion BVH that is what Isaac's RTX lidar does,
and the de-skew puts in the motion a real spinning lidar sees. With motion BVH, the renderer
may already trace each point from the sensor's pose at its firing time, so the de-skew moves
the points a second time. 0.108 m at 4.5 m/s is 24 ms, about half of a 50 ms revolution, which
is the mean offset that counting the motion twice over a revolution would give.

## The end state (133)

A real OS1 scans while it moves, so with the fix motion BVH may be the more faithful mode. The
end state is the de-skew skipped, or adjusted, when motion BVH renders each point from its own
pose. Motion BVH's effect on localization is then measured again, C6e2's pairing repeated.

## Steps (predictions written before each, when taken up)

1. Confirm what the render does with motion BVH. The probe: a lidar moving at a known speed past
   a wall square to its track, with motion BVH off and on, de-skew off. A wall square to the
   track shows the skew as a slant across the scan.
2. The fix in aib: the de-skew made aware of motion BVH (a rig or world setting), or skipped
   when Kit's `/renderer/raytracingMotion/enabled` is set.
3. C6e2's pairing again, on the fix.
