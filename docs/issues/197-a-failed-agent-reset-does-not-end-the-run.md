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

## The chain confirmed (118's D1 logs, 2026-11-27)

`home/2026-11-27 issue 197 D1 log lines (118)/i197_D1_lines.txt`:
- *relay:* `initialize -> OK: reset ego-1-1795745292 in progress` (at ...301.99), then
  `ego: reset ego-1-1795745292 -> FAILED in 17.0 s: the align landed off the scenario's heading 8
  times...` (...309.97). No other initialize or reset line: the concealer never called again.
- *scenario:* no `AutowareError`, no "Requested the service", no initialize or localization line
  (only the parameter dump: `initialize_localization` 10, `initialize_duration` 120).
- *agent:* `command reset -> FAILED...`, `phase INITIALIZING -> IDLE`, then 72 ms later
  `command set_goal` -> `goal set: (490.00, 1.62); engaging once ready` -> OK.
D1, D2 and D3 all ended `failed` at the timeout.

So steps 2 and 4 hold as written, and the logs add **a second fault: after a failed reset the
agent goes to IDLE and accepts the goal.** An agent whose reset failed has no valid pose and
should refuse a route until it is reset again.

## A's timing, before any code

Under A the concealer gets FAILED at once on each attempt, but its loop sleeps its interval
(10 s for `initialize_localization`) between attempts, and makes 30 (`requestInitialPose(...,
30)`): it would throw after about 300 s. A scenario with a shorter limit (this one's 150 s)
ends first, still `failed`, unless the scenario's time stands still while the concealer is
blocked. Which it does is the question A rests on; the interpreter runs Autoware's
initialization on the concealer's own task thread ("Hold the task queue"), so it may well
advance. To settle on a test run (one run, the draw config, a 150 s scenario) before choosing.

*A revised plan, both faults:*
1. The agent: a failed reset leaves it in a failed state (not IDLE) that refuses `set_goal` and
   `engage` with the reset's message, until the next reset. This alone stops the ego being
   driven from no pose, whatever the relay answers.
2. The relay: no OK for an unfinished reset (A), and a failed reset answered FAILED to later
   attempts at the same pose for a short while (one-shot for an OK, so a back-to-back rerun of
   the same scenario still resets).
3. If 2 is too slow against a scenario's limit, the run's result reads the relay's reset record
   and names the failure (the run is `error` by scensim's classifier rather than `failed`),
   whatever SSv2 does.
Tests first for 1 and 2; then the gate; then the live check.

## The strongest case, on CARLA (241, 2026-11-27)

241's Town01 run `2026-11-27T11-10-35_town01_ego_drive_r0` (the 58da5a69 build, the draws'
tolerance, so the reset fails by design): the agent's reset failed after eight aligns, the
agent took the goal anyway, the car moved at sim 97.6 s and reached it, and the run PASSED
(physical_verdict passed, 132 s). On Isaac's fixture_c6b the same chain ended at the
scenario's timeout; on CARLA the car stood where the truth put it, so nothing in the run
noticed. A failed reset that can pass is why the run must end on it (660c81eb) and the agent
must refuse the goal (f7de9207).
