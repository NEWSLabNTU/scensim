# 190: Autoware brakes only about 1 to 1.5 m/s^2 for a pedestrian darting into its lane

**Status:** open, a record (243; numbered by 133, 2026-11-26); no investigation yet.
**Severity:** to be judged. With room to stop, the Autoware ego kept a gentle deceleration
until it struck the pedestrian (issue 189's contact).
**Found:** 2026-11-26, scensim 243, 092 K9f-a's exit run 2 (k9f_zones, Isaac Sim 6.2).

## What happens

K9f-a's exit run 2, the asphalt case (`2026-11-26T05-50-10_goal_stop_goal_surface-asphalt_r0`,
`/var/tmp/aeon/k9fa-logs/k9f_zones/runs/`; the ego at `max_velocity` 11.11, scensim 72a629ea's
build): the ego peaks near 8.4 m/s about x 140 and brakes at about 1 to 1.5 m/s^2 from there on.
The pedestrian, triggered when the ego reached x 132, walks from y -126.5 into the lane at
x 112. At frame 492 it is at the lane's edge (y -128.3) and the ego is at x 121.7, 9.7 m away,
at 5.8 m/s: a stop at 4 m/s^2 needs about 4.2 m. The ego keeps braking at about 1 to 1.5 m/s^2
and meets the pedestrian at x 116.1 at about 3.5 m/s (frame 516, issue 189's contact). The ice
case (`2026-11-26T05-52-05_goal_stop_goal_surface-ice_r0`) is the same, meeting it at about
4.3 m/s.

Planning or perception, not the surface: on asphalt mu 1.12, and the braking asked never came
near either surface's limit.

## What to look at (not done yet)

When the pedestrian entered Autoware's objects (`/perception/object_recognition/objects`) and the
planner's stop reason in the run's record; whether the ego's brake request reached the vehicle
(aib's command against the truth's `command`); the scensim profile's deceleration limits.
