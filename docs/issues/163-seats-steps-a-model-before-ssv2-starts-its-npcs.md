# 163: seats steps a behaviour model before SSv2 starts its NPCs

**Status:** fixed 2026-11-25 (241; numbered by 133). **Severity:** medium: a model entity on
seats moves during the frames SSv2 holds its own NPCs still, so seats and the batch disagree
on every model without a start condition of its own.
**Found:** 2026-11-25, scensim 241, in 092 K13's exit check 3, run 1 (seats against the batch on
check 2's attempt 6 runs): the IDM follower's position differed by 4.73, 7.49 and 5.20 m, and its
`stopped` decision came 11 to 17 steps later in the batch, while the lead, SSv2's own vehicle,
agreed to 6.0e-5 m.

## What happens

SSv2 holds its NPCs until `startNpcLogic`: the frames before it (S, `scensim.truth.start_frames`)
are a pre-roll in which only the ego moves. The batch steps model entities from S on, as SSv2's
own NPCs (`BatchRun` with `start_frames=S`). The seats runner (`scensim.behaviour.seats.Runner`)
steps every model on every truth frame from the first, because the truth topic does not say
whether NPC logic has started (`TruthFrame` has no such field; only the gap trace records it).

K10's walker never showed it: its own start trigger (`start_gap`) held it until well after S.
The IDM follower has no start condition. On the decel 2 run it commanded from truth frame 2 and
moved from frame 3; at S (frame 11) it was 0.133 m on at 0.59 m/s, while the batch's follower
stood at its Init pose. The seats follower then ran 8 to 15 frames ahead of the batch's, a time
shift of 0.4 to 0.75 s, which at up to 9.9 m/s is the 4.7 to 7.5 m.

| run | S (frames) | follower max xy | `stopped`, seats / batch step |
|---|---|---|---|
| decel 2 | 10 | 4.73 m | 356 / 367 |
| decel 4 | 16 | 7.49 m | 340 / 357 |
| decel 6 | 11 | 5.20 m | 344 / 356 |

Evidence: `~/nas/autoveh/logs/k13-check3/run1/`.

## The interface change

`TruthFrame` gains `npc_logic_started`. truth-stream.md's versioning rule (section 3) is the
file's `schema` and covered no change to the topic's messages; section 4 now says how one is
handled. An addition changes the message's type hash: it lands with every reader in this
workspace in one build (here the bridge, the seats runner and scensim_isaac_world's
`ego_trace.py`, which reads the rows and stamps, not the new field), and an attachment built
against an earlier scensim_interfaces must be rebuilt, which the release notes say (v0.2.2,
"Interface changes"). No bag of the topic exists to convert. The file's schema stays 3: its
`frame` lines carried `npc_logic_started` already.

## The fix (133, 2026-11-25)

Seats is aligned to SSv2, not the batch to seats: a model is NPC logic, so the seats runner holds
it until NPC logic starts, with no step and no command, and the entity stands at its Init pose,
as SSv2 holds its own NPCs. The bridge publishes SSv2's `npc_logic_started` for each truth frame
(`TruthFrame.npc_logic_started`, the value the gap trace already records for the frame), and the
runner steps its models only on frames where it is true. In lockstep it still answers every frame
(an empty command set), so the tick gate never waits on it. Test: a model on seats does not move,
step or decide before S.

The run's command check (`scensim.truth.commands`, `result.json` `commands`) allowed one frame
before an entity's first command, the frame before the first answer. With the model held, the
frames before NPC logic carry no command by design: they are counted as `held_frames`, apart
from `uncommanded_frames`, and the lockstep rule is otherwise unchanged (found by check 2's
rerun after the fix: three error runs, lag 1 throughout, each with S + 1 frames before the
first command). Test: frames before NPC logic are held, and an uncommanded frame after it still
fails lockstep.

092 K13's exit check 2 is rerun after the fix (133), so its landed record describes this code.
