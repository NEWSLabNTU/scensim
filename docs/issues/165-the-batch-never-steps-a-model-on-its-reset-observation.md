# 165: the batch never steps a model on its reset observation

**Status:** fixed 2026-11-25 (241; numbered by 133). **Severity:** medium: every batch model
entity moved one step later than on seats, once issue 163 aligned seats with SSv2's NPC logic.
**Found:** 2026-11-25, scensim 241, in 092 K13's exit check 3, run 2 (seats with issue 163's fix
against the batch with issue 164's): the IDM follower's decisions came one step later in the
batch (`follow` at step 1 against 0, `stopped` 1 to 2 steps later) and its position differed by
0.48 m, about one frame at its 9.9 m/s.

## What happens

The batch steps a behaviour model inside `BatchRun.step`, after the ego's physics, and applies
its command the step after (the lockstep channel's lag 1, 092 K10). Its first decision is
therefore on step 1's observation, and its entity first moves at step 2. On seats (issue 163)
the model's first decision answers the first frame of NPC logic (seats frame S, batch step 0)
and moves the entity at S + 1, step 1, which is also where SSv2's own NPCs first move (the lead
moves at step 1 on both sides, within 6.0e-5 m). The batch skipped the decision on the reset
observation.

From the decel 2 run's pose dump (`~/nas/autoveh/logs/k13-check3/run2/dump-decel2.json`): the
seats follower first moves at step 1, the batch's at step 2; with the batch shifted by one step
the follower's largest error is 0.046 m, against 0.481 m unshifted.

Before issue 163 it could not show: the seats runner stepped models from the first truth frame,
and K10's walker waits for its `start_gap` far past S.

## The fix (133, 2026-11-25)

`BatchRun.reset` has each model decide once on the reset observation, for the reset slots only
(the models gate every state change on `valid`, here the reset mask), so its first command is
pending for step 1; nothing moves at reset. The decision's step is `model_dt`, `BatchRun`'s
`step_time` unless given; a scenario with model entities and neither is refused by name.
`ScensimEnv` passes its step. Test: after reset a batch model's first command is pending, its
event is recorded at step 0, and its entity first moves at step 1.
