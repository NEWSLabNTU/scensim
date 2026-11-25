# 185: aib's lidar point times are the read frame's, not the rendered frame's (0.1 s late)

**Status:** open; to be fixed as part 1 of issue 169's step 2 (133, 2026-11-25; plan first).
**Severity:** latent. No run publishes `point_format: xyzircaedt`, the only format that uses
these times. It must be fixed before that format is switched on (issue 169's step 2).
**Found:** 2026-11-25, scensim 118, after the result of issue 169's step 1, by instrumenting its
probe (labelled: found after the result, not predicted).

## What happens

With `xyzircaedt`, aib's `Lidar._msg` takes each point's firing time from the annotator's
`timestamp`, then:

- stamps the scan at the earliest of those times (`point_times`: `t0`, the header);
- distorts the cloud by `motion_distort(xyz, ts, t_ref, track)`, with
  `t_ref = clock - latency * frame_dt`, the frame the data was rendered in.

The annotator's times belong to the frame the data is read in, not the one it was rendered in.
In issue 169's probe (case B, 4.5 m/s, 20 Hz frames, `latency_frames` 2), at the last frame:
`t_ref` was 4.900 s, the track (the sensor's poses, a substep apart) ran to 5.000 s, and the
points' times ran from 5.000 to 5.050 s. The walls confirm that the data was rendered at 4.9 s:
the sensor was 0.45 m (v x 0.1 s) behind the root when the ahead wall was hit (A and C rows).

Two consequences, both measured in the probe:

1. Every point's time lies at or past the track's end, so `_pose_at` takes the last pose for
   all of them. aib adds no motion within the revolution (k 0.000 in B, where it should be 1),
   and it shifts the whole cloud by v x latency instead: B's walls were 0.450 m nearer than A's
   at 4.5 m/s, and D's 0.450 m nearer than C's.
2. A scan stamped from these times (the header at `t0`) would be 0.1 s late. With the default
   `xyzirc`, aib stamps from `self.stamps[0]`, the render frame's stamp, which is right.

## The fix (part 1 of 169's step 2, to plan)

Each point's time is the render's plus its offset within the revolution: `t_ref + (ts - min(ts))`,
the header at `t_ref`. Probe evidence: in C (motion BVH on) the ahead wall's points fired 12.25 ms
into the revolution, and the sensor was then at the render pose plus v x 12.25 ms (the lag
0.0876 s = 0.1 - 0.0124). So the revolution starts at the render, and the offsets are right.
