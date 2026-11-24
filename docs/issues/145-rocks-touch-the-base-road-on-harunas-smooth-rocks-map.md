# 145: rocks touch the base road on Haruna's smooth rocks map

**Status:** open; a bisection first (133). **Severity:** medium: issue 123's self-check fires, so
rocks rest on or fall to the world's own road and terrain instead of the true surface.
**Found:** 2026-11-24, scensim 118, issue 142's Haruna drives. Cross-linked with issue 136 (the
rough map's base contacts).

## What happens

One car, `fixture_cost --follow` on 086 C6b's *rocks* Haruna map (the smooth record road with
C6b's rock cover): issue 123's self-check logs rocks touching `/World/env/Road` or
`/World/env/Terrain` within their first second awake. Counts: siw issue-142 8547b30, 32 at
13.9 m/s (2.8 times real time) and 8 at 10 m/s (4 times), 9 at 10 m/s paced to real time; siw
main 56b8e39 (no 142) 9 at 10 m/s, about real time. Issue 128's guard, the same drive on siw
637b454 (10 m/s), found 0.

Between 637b454 and 56b8e39 lie issues 132, 134 (with the step split), 137, 139 and 140.

- **118's prediction (for the bisection):** 140's tile contact offset (0.02 m, rest offset 0)
  brings them: a loose rock rests on the collision tiles, and with the shorter reach its contact
  with a tile forms later, so a rock settling onto a steep tile face can pass it and meet the base.

## The bisection

The drive: `fixture_cost --follow`, one car, 10 m/s, 1900 frames, paced to real time (probe142c's
`PROBE142_REALTIME`), on the rocks Haruna map. GPU0, the quiet rule. Two runs a commit, as issue
141 asks of a start-sensitive count. The count is issue 123's self-check lines (`issue 123: rock
... touches the base road`).

- **Predictions (118, written before the runs):** 637b454: 0 and 0, as issue 128's guard found.
  87591b4 (139, the last before 140): 0 and 0. 56b8e39 (140): about 9 each, at least 5. So 140's
  offset brings them. If 87591b4 counts as many as 56b8e39, 140 is cleared and the next step is
  3a4fcd7 (134) against 6c6a044.
