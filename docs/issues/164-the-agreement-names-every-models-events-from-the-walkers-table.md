# 164: the agreement names every model's events from the walker's table

**Status:** fixed 2026-11-25 (241; numbered by 133). **Severity:** low: a tool's labels, but they
fail the agreement's decision check for any model other than the walker.
**Found:** 2026-11-25, scensim 241, in 092 K13's exit check 3, run 1: the batch side of the IDM
follower's decisions read `go` and `hesitate` where the seats side read `follow` and `stopped`.

## What happens

`scensim_batch.agreement`'s batch recorder turns a model's event codes into names with
`scensim.behaviour.walker.EVENTS`, whatever the model. The follower's codes are its own
(`scensim.behaviour.follower.EVENTS`: 1 `follow`, 4 `stopped`), so its 1 printed as the walker's
`go` and its 4 as `hesitate`. The decisions are compared by name, so the check fails even when
the codes and frames agree. The seats runner already names events by the model's own table
(`model.events`, the walker's only as a fallback).

## The fix

The recorder names each model's events from that model's `events`, as the seats runner does.
Test: a follower's codes 1 and 4 print as `follow` and `stopped`.
