# 190: Autoware brakes only about 1 to 1.5 m/s^2 for a pedestrian darting into its lane

**Status:** open (243; numbered by 133, 2026-11-26); offline reading done 2026-11-26, plan below.
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

## Amendment, 2026-11-26 (243): what run 2's records show, offline

Read from the two runs' gap traces alone (the truth carries Autoware's command per frame:
`entities.ego.command.acceleration` and `.velocity`). The runs recorded no bag and the planner
containers logged no stop reasons, so what perception saw is not in the record.

**Two corrections to "What happens" above.**

1. The gentle braking is the goal approach, not a reaction to the pedestrian. The route's goal is
   x 104, 8 m past the pedestrian's path (x 112). The command turns negative at frame 432 (x 143.6,
   8.5 m/s) and settles at -1.0 to -1.08 m/s^2 by frame 452. That is before the pedestrian moves:
   it first leaves y -126.50 at frame 460. Autoware's normal deceleration bound is
   `min_acc: -1.0` (`autoware_launch` 1.5.0, `planning/scenario_planning/common/common.param.yaml`),
   and a stop from 8.5 m/s over the 39 m to the goal needs 0.93 m/s^2.
2. Autoware did react, harder than 1.5 m/s^2, but late. In the asphalt case the commanded
   velocity breaks from the goal profile at frame 496 (6.02 to 5.22 m/s between frames 492 and
   496). The commanded acceleration reaches -2.08 at frame 500 and -3.08 at frame 504, then holds
   at -2.5 until the stop. -2.5 is the same file's limit bound (`limit.min_acc: -2.5`). The
   vehicle followed: from frame 504 to 508 the speed fell 4.83 to 4.23 m/s, 3.0 m/s^2 against
   3.08 asked. Actuation is not the problem. The ice case is the same shape 32 frames earlier:
   it breaks from the profile at frame 464 and holds at -2.5 from frame 472.

**The geometry, measured from the bumper.** The figure "9.7 m away" above is base_link to the
pedestrian's centre; it has issue 189's error. The Model 3's box runs 1.416 + 2.396 = 3.812 m
ahead of base_link, and the pedestrian is a 0.6 m box. At frame 492 the bumper is at x 117.84 and
the pedestrian's near face at x 112.30: a gap of 5.54 m at 5.84 m/s. Stopping in it would need
3.1 m/s^2 with no delay at all, which the -2.5 bound forbids (6.82 m). So once Autoware reacted
where it did, contact followed.

**When it reacted.** The ego's left side is at y -128.29 (centre -129.37, half width 1.08). The
pedestrian's near face reaches that line at about frame 488 (centre y -127.99). The command
changes between frames 492 and 496, 0.2 to 0.4 s later. Nothing in the command answers the
pedestrian before its body enters the ego's swept band, though it had been walking towards the
lane for 1.4 s (frame 460 onward). At frame 460 the bumper was 16.2 m from it at 7.49 m/s; a stop
at -2.5 then needs 11.2 m, leaving about 0.65 s for perception and planning.

**So the question 190 asks becomes:** why does the Autoware stack react only to an object inside
the ego's path, and not to a pedestrian whose predicted path crosses it? `motion_velocity_planner`'s
`run_out` module exists for exactly this and is launched by default (`tier4_planning_launch`
`motion_planning.launch.xml`, `launch_run_out_module` default true). Whether it ran in this stack,
and why it did not act, is open.

## Plan, 2026-11-26 (243): not started; each step needs 133's go

Offline first, no simulator:

1. Read the profile's planning launch and parameters (`autoware_sim_profile`), and record whether
   `run_out`, `obstacle_stop` and `dynamic_obstacle_stop` are launched and with what parameters
   (`run_out`'s object classes, its detection method, its deceleration limits). Read the live set
   from run 2's ego `play_launch.log` and its `load_node` list as well, since the record shows
   `motion_velocity_planner` loaded, but not its plugin list.
2. Read `map_based_prediction`'s pedestrian handling for a pedestrian away from a crosswalk (the
   pedestrian walks across at x 112, which is not on a crosswalk in Town01's lanelet2 map; to be
   checked against the map). If prediction keeps it on its sidewalk lanelet, `run_out` has nothing
   to stop for.

Then one recorded run on the same testbench (asphalt only; my CARLA nowhere near; Isaac alone,
with the memory guard), recording `/perception/object_recognition/objects` (the
objects with their predicted paths), the `motion_velocity_planner` debug
topics (its planning factors and `run_out` debug markers) and `/planning/scenario_planning/trajectory`.
Predictions, written now:

- P1: the pedestrian is in the objects within 0.5 s of first moving (by frame 470).
- P2: its predicted path crosses the ego's lane before frame 488.
- P3: if P1 and P2 hold, `run_out` either did not run or did not act; the planning factors say
  which. If P2 fails, the cause is prediction and `run_out` never had a crossing to answer.

What follows depends on which holds; any change to the profile is a separate roadmap step with
its own exit, not part of this issue.
