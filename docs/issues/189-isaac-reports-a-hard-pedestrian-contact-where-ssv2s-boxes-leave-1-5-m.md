# 189: Isaac reports a hard ego-pedestrian contact where SSv2's boxes leave about 1.5 m

**Status:** open, a record (243; numbered by 133, 2026-11-26); no investigation yet.
**Severity:** high. On Isaac a run can be judged `passed` over a real collision: the world
server's physics stopped the ego dead against a pedestrian, with an impulse of 5.5 and 7.6
kN s, while SSv2's `CollisionCondition`, which judges by the scenario's declared boxes, never
fired, since those boxes were still about 1.5 m apart. Any Isaac verdict that rests on SSv2's
collision (a scenario's contact failure, a judge's "no collision") can therefore read clean
when the simulated car struck something. CARLA is not known to be affected; not looked at.
**Found:** 2026-11-26, scensim 243, 092 K9f-a's exit run 2 (k9f_zones, Isaac Sim 6.2).

## What happens

In both cases of K9f-a's exit run 2 (`/var/tmp/aeon/k9fa-logs/k9f_zones/runs/`,
`2026-11-26T05-50-10_goal_stop_goal_surface-asphalt_r0` and
`2026-11-26T05-52-05_goal_stop_goal_surface-ice_r0`; scensim 72a629ea's build, roadmap 092,
K9f-a), the Autoware ego drives west along Town01's y -130 street and a pedestrian darts into its
lane at x 112. In both:

- the truth (the gap trace) has a `contact` with `ped`, `other_type` pedestrian, at the frame the
  ego's speed falls to zero within one 0.15 s window: asphalt frame 516, impulse 5470.5 N s
  (from about 3.5 m/s); ice frame 482, impulse 7595.5 N s (from about 4.3 m/s). Later frames
  carry small or zero impulses;
- at that frame the ego's body pose (`sim_pose`) is at x 116.1, and the pedestrian is at
  x 112.0, y about -129.5, on the ego's lane. With the Model 3's 4.7 m body box, its front is
  near x 113.8; the pedestrian's declared box is 0.6 m square. The boxes SSv2 judges are about
  1.5 m apart (not yet computed exactly with the origin offsets; `scensim.truth.closest` does);
- SSv2's `CollisionCondition` (ego with `ped`, the scenario's exitFailure) never fired: both runs
  `passed`.

So something in the Isaac world is larger than the declared boxes: the pedestrian's collider,
the car's, or both.

## What to look at (not done yet)

`scensim.truth.closest` on both runs, for the boxes' exact gap at the contact frame; the
pedestrian's and the car's colliders in the Isaac stage against their declared boxes; whether
CARLA shows the same with the same scenario; and which verdicts in past Isaac runs rested on SSv2's
collision alone.
