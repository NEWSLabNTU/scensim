# 190: Autoware brakes only about 1 to 1.5 m/s^2 for a pedestrian darting into its lane

**Status:** open (243; numbered by 133, 2026-11-26); plan steps (a) and (b) done 2026-11-26: the pedestrian box is UNKNOWN and its motion is not published, see step (b) below. What to change is 133's call.
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

## Plan step (a), 2026-11-26 (243): what the stack launches, read offline

Read from the installed Autoware 1.5.0 (`/opt/autoware/1.5.0/share/autoware_launch`, below
`AL`) and from `autoware_sim_profile` at the pin run 2 built (below `PROF`). No simulator ran.
Paths under `AL/config/planning/scenario_planning/` are shortened to `.../`.

**The detector.** Run 2's pilot is `{kind: autoware, args: {max_velocity: 11.11}}`
(`scenarios/projects/k9f_zones/testbench.yaml:29-30`), so it names no detector. The profile's
default is `lidar_detection_model` `clustering` (`PROF/launch/autoware.launch.xml:128`).
Euclidean clustering with shape estimation labels what it finds UNKNOWN, unless the tracker
gives it a class. The pedestrian here is a 0.6 x 0.6 x 1.8 m box (`isaac:box` in the gap trace's
entity record), not a person mesh. Whether it was labelled UNKNOWN or PEDESTRIAN is not in run 2's
record.

**Which modules run.** `PROF/launch/autoware.launch.xml:279` includes the profile's
`sim_preset.yaml` before autoware_launch includes its `default_preset.yaml`. A preset's
`arg` keeps the value set first, so the profile's choices win where both name an argument (the
profile's own comment, `PROF/launch/autoware.launch.xml:275-278`).
- `run_out`: on. The profile sets `launch_run_out_module` true (`PROF/config/planning/preset/sim_preset.yaml:76`,
  listed there among the behaviour velocity modules, where `run_out` lived before 1.5). Autoware's
  preset agrees (`AL/config/planning/preset/default_preset.yaml:124`). In 1.5.0 it is a
  `motion_velocity_planner` module.
- `dynamic_obstacle_stop`: on (`sim_preset.yaml:96`; `default_preset.yaml:115`).
- `obstacle_stop`: on (`default_preset.yaml:106`); the profile does not name it.
- `road_user_stop`: on (`default_preset.yaml:130`); the profile does not name it.
- `crosswalk` and `walkway`: the profile sets both (`sim_preset.yaml:43,46`); the pedestrian
  crosses at x 112, away from any crosswalk in this scenario.

**What each does with this pedestrian.**
- `run_out` stops for predicted collisions, but only with objects labelled PEDESTRIAN, BICYCLE or
  MOTORCYCLE (`target_labels`, `.../lane_driving/motion_planning/motion_velocity_planner/run_out.param.yaml:42`).
  It ignores an object already on the ego's trajectory footprint (`:48`; obstacle_stop's job) and a
  pedestrian on a crosswalk or walkway lanelet (`:73`). Its stop may brake up to 5 m/s^2 before it
  is reported as an error (`:31`). An UNKNOWN object is not a target at all.
- `road_user_stop` takes pedestrians (`road_user_stop.param.yaml:35`) but not UNKNOWN (`:38`).
- `obstacle_stop` ignores crossing obstacles (`obstacle_stop.param.yaml:5`,
  `ignore_crossing_obstacle: true`). For UNKNOWN objects it checks only those inside the ego's
  footprint (`check_outside`, `unknown: false`, `:58-60`), widened by a 0.3 m lateral margin (`:72`).
  It names a deceleration limit of -1.2 for UNKNOWN (`:37-38`).
- `dynamic_obstacle_stop` names no label filter in its parameters; it takes objects moving above 0.5 m/s (`dynamic_obstacle_stop.param.yaml:5`),
  but only beyond 1.0 m of the ego's footprint (`:11`), only after 0.5 s of continuous detection
  (`:9`), and ignores collisions it judges unavoidable by stopping (`:12`).
- `map_based_prediction` predicts pedestrians and UNKNOWN objects 10 s ahead
  (`AL/config/perception/object_recognition/prediction/map_based_prediction.param.yaml:5-6`); its
  crosswalk logic applies to pedestrians near a crosswalk (`:10-12`), which this one is not.

**What this suggests, a hypothesis for (b), not a finding.** If the box was labelled UNKNOWN,
then `run_out` and `road_user_stop` could not see it. `obstacle_stop` sees it only once its body
is within 0.3 m of the ego's swept band. That happens at about frame 484 (centre y -127.69); the
command changed between frames 492 and 496. That fits the record: no answer during its walk,
then a stop once it was in the path. `dynamic_obstacle_stop` may have seen it during the walk and
then dropped it. With a stop limit of 2.5 m/s^2 the collision was unavoidable from frame 492,
and `:12` tells it to ignore such collisions.

One thing does not fit: the command reached -3.08 and held -2.5, beyond the -1.2 that
`obstacle_stop` names for UNKNOWN (`:38`). Either that limit does not bind with
`suppress_sudden_stop: false` (`:6`), or another module made the stop. The planning factors in
(b) say which.

**Predictions for (b), amended 2026-11-26 (243) before any run.** P1 to P3 above stand. Added:
- P4: the pedestrian box is labelled UNKNOWN in `/perception/object_recognition/objects` for
  most of its walk.
- P5: if P4 holds, the stop comes from `obstacle_stop` (its planning factor), and `run_out` shows
  no decision for the object.
- P6: if P4 fails (labelled PEDESTRIAN), `run_out` shows a collision for it before frame 488,
  and the question becomes why it did not stop. Its ignore rules (`:48`, `:73`) come first.

A natural check of the label's effect is the same run with a person-shaped pedestrian or with
`lidar_detection_model:=centerpoint`. That is a separate run for 133 to decide, after (b).

## Plan step (b), 2026-11-26 (243): the recorded run, and what it shows

**The run.** `2026-11-26T13-20-19_goal_stop_goal_surface-asphalt_r0`, 13:20 to 13:21 on
newslab-server243, Isaac Sim 6.2. It used the K9f-a gate's install (scensim 91d3e9ab;
91d3e9ab..f95ead0f is docs only), on a copy of k9f_zones with `logging.capture: full` and a
`logging.topics` list, asphalt case only. The run directory, its bag, the decoder and its output
are on the NAS, `home/2026-11-26 190 b run (243)/` (with SHA256SUMS). The decoder is `bag190.py`,
run with Autoware 1.5.0 sourced.

The verdict is failed: `SimulationFailure: ... "ego_hits_ped"`. This time SSv2's own collision
condition fired, unlike run 2 (issue 189). The contact report holds one contact, `ped`
(pedestrian), first at SSv2 frame 538, max impulse 6189.7 N*s. Under the contact judge on main
since 4dacfd6f, an undeclared actor contact at any impulse, this run fails the same way. That is
not a new failure.

**Recorded and not.** The bag holds the objects (`/perception/object_recognition/objects`, 253
messages), the tracked objects (253), and the planning factors of seven of the nine modules
named (219 each). `obstacle_velocity_limiter` and `boundary_departure_prevention` published none.
It also holds both trajectories, both control commands, the kinematic state and the vehicle
status. Three things were not recorded:
- `/perception/object_recognition/detection/objects`;
- the motion_velocity_planner's `debug/markers` (0 messages);
- the per-module `debug/<module>/debug_markers`.
Those names were read from the libraries' strings and do not match the live ones. Nothing below
depends on them.

**Times.** Sim seconds from the episode's start; the bag's stamps minus the 1000 s base. The
pedestrian appears at the trigger and is in the objects by 24.25 s. It first moves at frame 486
(24.25 s) and walks from y -126.5 towards the lane at about 1.5 m/s. The ego's left side is at
y -128.3.

**The objects: P1 and P4 hold, P2 fails.** At every message from 24.25 s to the contact, the
pedestrian box is one object labelled `UNKNOWN` with probability 1.00, its position tracking the
truth (y -126.55 at 24.25 s, -127.89 at 25.65 s, -129.09 at 26.50 s). Its velocity is
**(0.00, 0.00)** in both the tracked and the predicted objects throughout. So its one predicted
path (confidence 1.00) stays where the object is: at 25.65 s it starts and ends at
(112.0, -127.9). The predicted path never crosses the lane while the object is still outside it.

The reason is in Autoware 1.5.0's tracker parameters
(`AL/config/perception/object_recognition/tracking/multi_object_tracker/multi_object_tracker_node.param.yaml:18-19`):
`enable_unknown_object_velocity_estimation: true` and `enable_unknown_object_motion_output: false`.
The tracker estimates an UNKNOWN object's velocity but publishes it as zero. The profile's
generated copy carries the same values
(`PROF/config/perception/object_recognition/tracking/multi_object_tracker/multi_object_tracker_node.param.yaml:21-22`).

**The planner: P3's second branch, and P5.** P2 failed, so the cause is perception: no module had a
crossing to answer. Every module that names a stop condition sees a still object off the path:
- `run_out` excludes UNKNOWN by label (`run_out.param.yaml:42`);
- `dynamic_obstacle_stop` ignores objects slower than 0.5 m/s (`dynamic_obstacle_stop.param.yaml:5`),
  and this one reads 0;
- `obstacle_stop` checks UNKNOWN only inside the footprint (`obstacle_stop.param.yaml:58-60`).

In the window from 23.0 s to 27.2 s, only `obstacle_stop` published a planning factor; the six
others published empty factor lists. Its first factor is at 25.70 s (behaviour 3, a stop), with
the stop point 0.9 m ahead of the ego. The object's centre is at y -127.89 to -128.08 then: its
near face is inside the ego's left side plus the 0.3 m lateral margin (`:72`). From 25.80 s the
stop point lies behind the ego (distance -0.0, then -0.7 to -4.9 m). The stop came from
`obstacle_stop`, and `run_out` showed no decision, as P5 predicted.

**The -3.08 misfit, resolved in part.** As in run 2, the command goes past `obstacle_stop`'s
-1.2 limit for UNKNOWN: -1.23 at 25.75 s, -2.00 at 26.05 s, -3.00 at 26.25 to 26.30 s, then -2.50
until the stop. Only `obstacle_stop` asked for a stop, so no other module explains it. The stop
point it planned was already at or behind the ego from 25.80 s. A stop the -1.2 limit cannot
reach in time is still planned (`abandon_to_stop: false`, `:41`), and the deceleration beyond
-1.2 comes from downstream of the planner. Which stage sets -3.00 and then -2.50 (the velocity
smoother's `limit.min_acc` -2.5, or the controller) is not in these topics.

**Times against run 2.** The ego reached the trigger at 7.6 m/s and passed x 121 at 5.8 m/s,
as in run 2. The first `obstacle_stop` factor (25.70 s) came 1.45 s after the pedestrian started
walking (24.25 s); in run 2 the command changed 1.6 to 1.8 s after. Contact came at 26.9 s
(frame 538).

**What follows, for 133.** The pedestrian box is UNKNOWN, and UNKNOWN motion is not published,
so no module can see the crossing coming. These would change that:
- `enable_unknown_object_motion_output: true` in the profile. `dynamic_obstacle_stop` could then
  see a 1.5 m/s object; `run_out` still could not, by label.
- A pedestrian that perception labels PEDESTRIAN: a person-shaped asset, or
  `lidar_detection_model:=centerpoint`. `run_out` and `map_based_prediction`'s pedestrian paths
  then apply.

Each would be its own step with its own predictions, not part of this issue. The first changes
Autoware's behaviour for every UNKNOWN object in every scensim run, so it needs a decision on the
profile, not only on this scenario.

## Correction, 2026-11-26 (243): the pedestrian wears a walker

Step (a) above says the pedestrian is "a 0.6 x 0.6 x 1.8 m box ... not a person mesh". That is
wrong for what the lidar sees. The gap trace's `asset: isaac:box` names the collider. The Isaac
world server dresses every pedestrian in a CARLA walker (roadmap 044 C,
`scensim_isaac_world/world.py`, `walker_gait.pick`; `vehicle_assets.add_walker_body`) and makes
the box invisible. Run (b)'s world server log says so: `first bp_walker_male_eurow_owv_v2 in this
world server: rendered in 3.7 s`. So the lidar saw a person-shaped, animated mesh, and
`clustering` still labelled it UNKNOWN. Euclidean clustering with shape estimation gives no class
from shape. Step (b)'s conclusions stand, since they rest on the label and on the zero velocity,
not on the shape.

## Plan, steps (c) and (d), 2026-11-26 (243): before any run

The user's choice, through 133: measure both changes separately on the same case (goal_stop,
asphalt), with run (b) `2026-11-26T13-20-19_goal_stop_goal_surface-asphalt_r0` as the baseline,
then decide.

**What is recorded.** The same topics as (b), with the three empty ones replaced:
- the motion_velocity_planner's debug markers recorded under both patterns its libraries' strings
  allow (`<node>/debug/<module>/debug_markers` and `<node>/<module>/debug_markers`);
- `/perception/object_recognition/detection/objects`, kept;
- `/perception/object_recognition/detection/centerpoint/objects` for (c).
A `ros2 topic list` of the ego's domain is taken once the pilot is ready, so the right names are on
record for the next run.

**Step (c): stock Autoware, a pedestrian perception labels PEDESTRIAN.** The cheaper route, a
person-shaped asset, is already in place (the correction above) and does not change the label. So
(c) is `lidar_detection_model:=centerpoint` (full CenterPoint, the profile's choice for it) on the
same walker. It is set as the pilot's argument in a copy of the testbench, beside
`max_velocity: 11.11`. TensorRT 10.8.0 is at `/var/tmp/aeon/tensorrt-10.8.0/lib`, set as
`autoware.tensorrt_lib` in that copy's host settings; its two engines are on the host
(`~/autoware_data/lidar_centerpoint/`). The card floor and the guard are as in (b);
CenterPoint adds about 600 MiB at peak.

Predictions for (c):
- C1: CenterPoint labels the walker PEDESTRIAN (highest probability) for most of its walk, from
  within 0.5 s of its first movement. This is the least certain of the four: CenterPoint was not
  trained on Isaac's RTX lidar returns from a CARLA walker.
- C2: its tracked velocity is non-zero and within 0.5 m/s of its 1.5 m/s walk while it walks, and
  its predicted path crosses the ego's lane.
- C3: `run_out` publishes a stop or slowdown factor for it before it reaches the ego's side line
  (in (b), at about 25.65 s, 1.4 s after it starts walking).
- C4: the ego stops without contact. This is less sure than C3. At the walk's start the bumper is
  about 16 m away at 7.4 m/s. A stop at -2.5 needs 10.9 m, plus `run_out`'s 2.5 m distance buffer
  and about 0.6 s of on-time buffer and tracking, about 17.8 m in all. So a contact at low speed
  (under 2 m/s) is about as likely as none.

**Step (d): the tracker publishes an UNKNOWN object's motion.** `enable_unknown_object_motion_output:
true`, with clustering kept, for this testbench only and not as the profile's default. On Autoware
1.5.0 the profile passes the tracker its parameter file as a fixed value
(`PROF/launch/components/tier4_perception_component.launch.xml:230-231`), so no run-time argument
reaches it today. The narrow route is a profile launch argument for that file, its default
unchanged, which the testbench sets to a copy with the one value changed. That is a change to
`autoware_sim_vehicle` (its own commit, pins, `just gate`), so it waits for 133's go.

Predictions for (d):
- D1: the walker stays UNKNOWN, and its tracked velocity is non-zero (about 1.5 m/s across the
  lane) from within 1 s of its first movement.
- D2: `dynamic_obstacle_stop` publishes a stop factor for it before `obstacle_stop`'s first one,
  and before it reaches the ego's side line.
- D3: `run_out` publishes no factor for it (UNKNOWN is not in its `target_labels`).
- D4: contact is no less likely than in (c). `dynamic_obstacle_stop` needs 0.5 s of continuous
  detection and drops collisions it judges unavoidable (`dynamic_obstacle_stop.param.yaml:9,12`),
  so it may act and then let go.

**The comparison** for the user, after both: per run, the label, the velocity, which module
stopped and when (relative to the walk's start), the peak commanded deceleration, the speed at
contact or the stop distance, and the verdict, against (b).

**Amendment to (c)'s predictions, 2026-11-26 14:08 (243), before the run.** The profile's
`use_multi_channel_tracker_merger` defaults to true (`PROF/launch/autoware.launch.xml`, issue
028). With centerpoint, the tracker then takes only CenterPoint's objects and
detection_by_tracker's, so an object CenterPoint does not detect never reaches planning:
clustering's UNKNOWN is not a fallback. Hence:
- C0: if C1 fails because CenterPoint does not detect the walker at all, the objects hold
  nothing for it and no module stops for it, not even `obstacle_stop` (b's late stop). The ego
  then meets it at near goal-approach speed (about 6 m/s rather than b's 3.5).
- C1, stated more fully: the walker is in the objects, labelled PEDESTRIAN, for most of its walk.
Full CenterPoint needs about 2.05 GB of VRAM at peak against tiny's 1.46 (CLAUDE.md), so (c)'s
card floor is 14336 MiB, 2048 above (b)'s 12288.
