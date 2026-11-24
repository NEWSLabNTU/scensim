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

### The bisection's result (2026-11-24)

The prediction fails. Each of the six runs counts 9, on every commit, and they are the same nine
rocks (r136, r154, r160, r188, r192, r196, r422, r561, r623); only which base prim each touches,
the road or the terrain, varies between runs. Every run drove 1020 m and exited 0. Nothing between
637b454 and 56b8e39 brings them, 140's offset included.

| siw | run 1 | run 2 |
|---|---|---|
| 637b454 (128's guard) | 9 | 9 |
| 87591b4 (139, before 140) | 9 | 9 |
| 56b8e39 (140) | 9 | 9 |

Issue 128's 0 was a shorter drive, not another result: its guard ran fixture_cost's default 400
frames, which ended at 280.3 m along the course. Here the first two contacts (r136, r188) come at
about 282 m in all three commits, and the rest at about 365 to 390, 490 to 500, 600 to 615 and
865 to 875 m. (The along-course place is the car's at the log line's second, so it is good to
about 10 m.) The self-check at 637b454 counts these 9 too, so the contacts are at least as old as
128's guard, and the guard never drove far enough to see them.

What this leaves open: the contacts' cause on this map, and their growth with speed (9 at 10 m/s,
36 at 13.9 m/s paced, issue 142's like-for-like). Each 1 s window has the base reach a rock that
the detail tiles should hold, so the next step is what is under those nine rocks when they wake.
Every log also ends on the tile worker's `BrokenPipeError` in `pickle.dump`: the worker writes a
result after the app has closed its pipe at exit. It comes after the drive's summary and is not
part of the count.

The run record: `/mnt/renegade/aeon/isaac-ex/c6b-140/run145.sh`, `b145_*.log`, `b145_*.jsonl`.

## The diagnosis (before the runs)

133's step, with the same drive on siw main 77075e3: one run at 10 m/s and one at 13.9 m/s,
both paced to real time, in a scratch probe (`probe145.py` over probe142c). For every rock woken:
its lowest point against the base and the detail tile under it, from PhysX scene queries straight
down. For every base contact: the same at its pose then; the contact points and separations from
that step's report; the frames since it woke; the USD state of the filter (the prim in `rocks`'
includes or still pending, `rocks` filtering `roadBase`, the base among `roadBase`'s members); and
where it lies (its tile and the distance to the tile's edge, and its corridor's v against the
carriageway's half width and the shoulder). On a smooth record there are no potholes, so a seam
means a tile edge.

A rock in `rocks` and a base in `roadBase` cannot touch while the filter holds, whatever the
geometry. So the geometry says where they touch; whether they may touch at all is the filter's.

- **118's prediction.** The USD state is right at every contact: the prim in `rocks`, nothing
  pending, `rocks` filtering `roadBase`, the base a member. Of two readings:
  - (a) PhysX does not apply the filter to any of these rocks, so the geometry decides: every
    woken rock whose lowest point comes within the pair's contact reach of the base reports;
    the rest lie further above it;
  - (b) PhysX does not apply the filter to particular prims only: woken rocks lie as close to the
    base as the nine do and do not report;
  118 expects (a). The nine lie where the base comes up to or above the detail surface: off the
  carriageway (|v| beyond the half width), where the world's terrain meets the detail's shoulder
  or ditch, not at a tile edge. Their lowest point is at most a few cm above the base, and the
  contact separations are 0 or small, not deep.
- **Speed.** At 13.9 m/s more rocks wake (the activation window grows with speed, and a faster
  car knocks more), and the hits are the 10 m/s run's nine plus others of the same kind. A
  rock reports at most once per wake (the check stops at its first hit), so the count grows with
  the wakes, not with repeat touches.
