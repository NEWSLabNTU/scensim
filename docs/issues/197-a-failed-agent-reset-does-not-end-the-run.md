# 197: a failed agent reset does not end the run

**Status:** open; a plan, no code (133, 2026-11-27). **Severity:** medium. When a vehicle agent
fails its reset (here: issue 195's change, eight missed aligns), the scenario does not end in
error naming it: the ego stands still and the run ends `failed` at the scenario's own timeout,
its judges passed, with nothing in the result saying why. **Found:** 118's issue 195 draw run D1
(fixture_c6b, 58da5a69 with `yaw_tolerance: 1.0e-6`, 2026-11-27): after `align 8 of 8` the
run went on and ended `failed` by its 150 s timeout. 243's draw design had assumed an error.

## The path, from the code (to be confirmed in the runs' logs)

1. SSv2's concealer initializes localization through the AD API,
   `requestInitialPose(..., 30)` (`concealer/src/field_operator_application.cpp`): up to 30
   attempts, each waiting `initialize_localization` (10 s) for a reply; a reply with
   `success` false moves to the next attempt; after 30 it throws `AutowareError`, which ends the
   run in error (`concealer/service.hpp`).
2. The relay answers it (`relay_node.py` `_on_initialize`, `episodes.py` `Episodes.initialize`):
   it starts the agent's reset (or joins one running at the same pose) and waits `SLOW_REPLY`
   (9 s). **If the reset has not finished, it answers OK, "reset ... in progress".** A reset of
   eight aligns takes longer than 9 s, so the concealer is told the initialize succeeded.
3. The concealer then waits for Autoware's state and for the estimate to reach the pose
   (`waitForLocalizationToReach`: 1.0 m, **0.2 rad**, 10 s). The agent's failed reset leaves the
   estimate at its last align, within the position bound and 0.04 to 0.08 rad off (D1): the
   concealer's 0.2 rad accepts it, and the scenario goes on as if the ego were localized.
4. The reset's failure is recorded by the relay (`record_reset`, its log `reset ... -> FAILED`),
   but no call carries it back to the concealer. The agent, failed, takes no route; the ego
   stands; the scenario's `SimulationTimeCondition` ends it as `failed`.

*To confirm in 118's D1 records:* the relay's log has `initialize -> OK: reset ... in progress`
and later `reset ... -> FAILED in ... s: the align landed off the scenario's heading 8 times`;
the concealer's log has no `AutowareError`; the agent never receives a goal (or refuses it).

Before 195 this path was rare: a reset failed only after `reinitialize_attempts` lost scans or a
`converge_timeout`, and the concealer's own checks often failed with it. 195's tighter bound makes
a failed reset whose last estimate still passes the concealer's 0.2 rad the common case.

## What the run should do instead

End in error at the reset, with the agent's message in the result: a failed reset means the ego
was never placed, so no verdict about its driving is valid.

## Options (plan only)

**A. The relay does not answer OK for a reset still running.** It answers `success` false with
"in progress": the concealer tries again (10 s later, up to 30 attempts, 300 s), each attempt
joining the running reset; when the reset ends, the next attempt gets its final status. On OK,
as today. On FAILED, the relay keeps the failed record for that pose and episode and answers
every later attempt FAILED at once with the agent's message, so the concealer exhausts its
attempts and throws: the run ends in error. *For:* the protocol already carries the status; no
SSv2 change; the relay's record and log name the cause. *Against:* the concealer's error text is
generic ("Requested the service ... 30 times"), so the run's classifier should also read the
relay's reset record to name it; a reset over 300 s (issue 046 saw 76.5 s) would be cut off.

**B. A failed reset withholds localization.** The agent (or the relay's mapping) reports the
localization as not initialized and withholds the estimate after a failed reset, so the
concealer's `waitForLocalizationToReach` times out (10 s) and throws. *For:* fast. *Against:* it
relies on the concealer's 10 s wait rather than on the reply, and the message is lost the same way.

**C. The bridge ends the run on the relay's reset record.** *For:* names the cause directly.
*Against:* the bridge does not read the relay today; a new coupling.

**Recommendation (243):** A, with the run's result reading the relay's reset record for the
message. **Steps, once chosen:** confirm the path in 118's logs (above); a failing test in the
relay's tests (a reset that fails after the reply window answers FAILED to the next attempt and
every later one); the change; the gate; a live check with 195's draw config, predicting an error
ending within 300 s that names the agent's message.
