# 130: the batch's truth playback puts the seats ego's actor pose where the entity's belongs

**Status:** fixed: the playback and the seats attachment read the entity's pose. Found 2026-11-24 by 241 in 092 K11b's check 4.
**Severity:** medium. The ego's box in the batch is 1.387 m ahead of where seats has it, for
every frame of an `--ego-from-truth` run. Box geometry on the ego is shifted by that much: the
closest gap, contacts, and storyboard conditions measured to the ego.

## What happened

K11b checks the batch's closest gap (`python3 -m scensim.truth outcomes` on the batch's truth
export, the same `closest()` the seats judge runs) against the seats judge, on K10's
agreement runs: set 3's L seeds 2 and 31, replayed with `agreement_run.py --ego-from-truth
--truth-out`. The closest gaps agree within 0.05 m, as check 4 asks:

| Run | Seats | Batch | Difference |
|---|---|---|---|
| L seed 2 | 0.443 m (frame 141, 7.00 s) | 0.488 m (step 123, 6.15 s) | +0.045 m |
| L seed 31 | -1.231 m (frame 131, 6.50 s) | -1.262 m (step 116, 5.80 s) | -0.031 m |

But the minima fall at different frames (S = 14, so seats frame 141 is batch step 127, not
123), and frame by frame the gaps do not agree. L seed 2, seats frame S + k against batch step k:

| k | Ego box centre, batch | Ego box centre, seats | Gap, batch | Gap, seats |
|---|---|---|---|---|
| 0 | (317.838, -129.512) | (319.225, -129.512) | 36.604 | 37.989 |
| 110 | (281.539, -129.496) | (282.926, -129.497) | 0.559 | 1.714 |
| 123 | (276.124, -129.494) | (277.511, -129.494) | 0.488 | 0.488 |
| 127 | (274.457, -129.493) | (275.844, -129.494) | 1.594 | 0.447 |

The walker's box agrees to 1.2e-4 m at every k, as K10 measured. The ego's box is 1.387 m ahead
along its heading (it drives toward -x) at every k. 1.387 m is the ego's `origin_offset` in the
seats truth: the CARLA actor's origin ahead of the entity's.

## Why

`scensim_batch.agreement.ego_states` gives `TruthPlayback` each frame's `sim_pose`, the
simulator's pose of the actor. The batch's ego state is the entity's pose (its box is
`declared.center` from it), and its truth export writes `origin_offset` 0. The seats truth
takes the offset back off (`scensim.truth.boxes`, `gap_geometry.entity_pose_from_actor`);
the playback does not. So the batch places the entity where the actor is.

K10's agreement did not see it: it compares the ego's pose as each side records it (the actor's
on both), and the walker's model on seats reads the truth topic's poses, which carry the same
`sim_pose`, so both sides' walker saw the same ego. The closest gaps agreed only because the
shifted box finds its minimum at another frame.

## Decision (133, 2026-11-24)

**A behaviour model reads the entity's pose**: the scenario's frame, what SSv2's conditions and
the batch's engines use, and what the model's gap means. So both sides take the offset off:

- the playback (`scensim_batch.agreement.ego_states`), for the batch's ego state;
- the seats attachment (`scensim.behaviour.seats`), which now reads each entity's
  `origin_offset` from the latched `/scensim/truth/entities` and takes it off every pose before
  a model sees it (an entity whose offset has not arrived is absent for that frame).

**Velocities, the same point on every side.** The batch's engines give the entity origin's
velocity: engine A aib's `base_link` velocity, engine B the articulation root link's
(`root_link_vel_w`), whose frame is `base_link`, the rear axle's centre (sim_vehicle_spec's
articulation file: `frame: base_link`, the chassis box centred 1.416 m ahead of it, the
declared box's centre). Seats' truth carries the body origin's, 1.387 m ahead. A rigid body's
two points differ by w x r: |dv| = 1.387 m x |yaw rate|, across the heading (0.14 m/s at
0.1 rad/s, 0.42 m/s at 0.3 rad/s). So the playback and the seats attachment take that off too,
from the truth's yaw rate: v_entity = v_body - w x r. On K10's CS1 runs the ego drives
straight (yaw rate 0 at every frame), so this changes nothing measured there.

## Effect on landed results

K12's exit (set 3) and K10's agreement (runs 1 and 2) compared like with like: the actor's pose
on both sides. They stand as the channel's and the agreement's results. But the walker's
decisions in those runs were made against an ego 1.387 m ahead of its entity, on both sides
alike. A rerun of their decision frames is not needed for those exits: what they checked, the
lag and the two sides' agreement, does not depend on which pose both read.

K12's recorded check 2 results stand as measured with the tool of their day:
`k12_walker_replay.py` then read the ego's body pose, as the seats runner did. Since 2026-11-24
(243) it reads every entity through the runner's own conversion (`seats.entity_pose`,
`seats.entity_velocity`). Before that change it disagreed with the fixed runner on K10's recheck
runs (each event 3 frames early, 0.210 m); after it, on the same two runs (L seeds 2 and 31,
scensim dcce0cdb): max xy error 1.49e-4 m on each, events on the same frames.

## The fix

- `ego_states` takes the offset off with `gap_geometry.entity_pose_from_actor`, as
  `scensim.truth.boxes` does. Test (`test_playback.py`): the played-back ego's box equals
  `boxes()`' box on the seats truth at every frame, to 1e-12 m.
- `seats.frame_of(msg, offsets)` takes it off for every entity. Test
  (`test_behaviour_seats.py`): on a truth whose body is 1.387 m ahead, the model's ego is the
  entity pose `boxes()` builds the ego's box from.
- Both also take w x r off the velocity. Tests: a turning body's velocity becomes the entity
  origin's, in the playback and in the attachment.
- K11b's check 4 is rerun per frame (roadmap 092, "K11b's check 4").
- **K10's open recheck** (roadmap 092): two new seats runs (L seeds 2 and 31 of
  `k12_commanded`) with the fixed attachment, then the agreement on them, its prediction
  written first: decisions at the same frames. Not optional: K10's "decisions agree" rests on
  code both sides have changed.
