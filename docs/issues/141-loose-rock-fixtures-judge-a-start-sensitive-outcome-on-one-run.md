# 141: the loose-rock fixtures judge a start-sensitive outcome on a single run

**Status:** open, a record; no work now (133). **Severity:** medium: a verdict that flips on an
unrelated change says nothing about the change. **Found:** 2026-11-24, scensim 118, issue 140's
proof runs.

## What happens

086 C6b's loose_15 fixture (`rock_check`: the rock moves at least 5 cm, is not lost, is no
faster than the car) is judged on one drive per query. Its outcome turns on small changes:

- issue 122 showed it turns on the car's start;
- issue 140's tile contact offset (0.02 m on the detail collision tiles, nothing else changed)
  flipped it in both queries: raycast from passes (moved 1.674 m) to fails (2.3 cm), sweep from
  fails (2.5 cm) to passes (0.288 m). loose_8's sweep move went from 5.0 to 1.2 cm (failing
  both times). The same fixtures on the siw without the offset gave 128's numbers to the digit,
  so the offset moved them; but a rock that either rolls off or stays put on a few mm of contact
  is a coin, and one toss is not a verdict.

## The cure (not started)

Judge the loose-rock fixtures over several runs, each with a small, recorded change of start
(issue 122's sensitivity), as a pass share against a bar written before the runs, and report the
spread of the move beside it. embedded_15 and boulder_35 repeat to the digit and stay single-run.
