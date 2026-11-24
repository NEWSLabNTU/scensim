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

### The diagnosis's result (2026-11-24)

siw main 77075e3; the 10 m/s run drove 1020 m and the 13.9 m/s run 1328.5 m of the 1527 m
course (1900 frames each, as the bisection). Both exited 0. Record: `run145d.sh`, `probe145.py`,
`d145_77075e3_v10.*`, `d145_77075e3_v139.*`.

| | 10 m/s | 13.9 m/s |
|---|---|---|
| rocks woken (first wakes) | 9 | 37 |
| of them touching the base | 9 | 37 |
| wakes again (the check runs once a rock) | 0 | 17 |
| on `/World/env/Road`, least separation | 5, -2.5 to 1.9 mm | 14, -3.7 to 3.5 mm |
| on `/World/env/Terrain`, least separation | 4, 74 to 112 mm | 23, 67 to 88 mm |
| across the road, \|v\| | 3.29 to 3.56 m, all right | 3.26 to 4.00 m, 24 right, 13 left |

- **Every rock that woke touched the base, in the very physics step it woke** (0 frames awake at
  every hit), 46 of 46 first wakes in the two runs. The self-check counts the rocks woken, once
  each: a rock woken again is not checked again.
- **The USD state was right at every hit.** The prim was in `rocks` (768 to 770 members), with
  nothing pending to add or drop, `rocks` filtered `roadBase`, and `roadBase` held
  `/World/env/Terrain`, `Road` and `Lines`. So PhysX made a pair the filter should have killed.
- **Where they lie.** Every one is on the shoulder: \|v\| from 3.26 to 4.00 m, against the
  carriageway's half width of 3.25 m and the shoulder's 0.75 m (C6b's cover puts no rocks on the
  carriageway). Their distance to a tile's edge spreads from 0.08 to 7.2 m, so a seam plays no
  part; the smooth map has no potholes. Each rock rested on its tile, its lowest point within
  4 mm of the tile's surface (one at 7 cm, the 13.9 m/s run's only one). On this map the base
  coincides with the tile there: the base was within 6 mm of the rock's lowest point. On the
  Road the contacts touch (separations of a few mm either side of 0). On the Terrain they are
  within the pair's contact reach, 7 to 11 cm, without touching.
- **Speed.** The count grows because more rocks wake, not because the same rocks touch more
  often. At 13.9 m/s the car woke rocks on both shoulders (why its path came nearer the left
  shoulder is not measured) and drove further (1328.5 m against 1020). The activation window hardly differs (0.6 s
  of travel ahead, at least 8 m: 8 m at 10 m/s, 8.3 m at 13.9). Six of the 10 m/s run's nine woke
  and touched again; three did not wake at all.

**118's prediction, as measured:**

- The USD state: held.
- Reading (a) against (b): (a) held. No woken rock lay as close to the base as the hits without
  touching it; every woken rock touched.
- Where: partly held. They are off the carriageway, on the shoulder, and not at tile edges, as
  predicted. But the base does not come up above the detail: base and tile coincide to the mm
  there. The contact separations are 0 or small, as predicted.
- Speed: partly failed. More rocks wake, as predicted. But they are not the nine plus others
  (three of the nine did not wake). And a rock reports at most once per run, not once per wake,
  so the count is the number of distinct rocks woken.

**What it says.** An asleep rock is a static collider, and two static colliders never make a
pair. So a missing filter would show only when a rock wakes, and then at once. That is what all
46 do. This points at the filter on the rock as PhysX takes it when its body is enabled (asleep
to awake), not at the geometry. On this map it does no harm: the base and the tile agree on the
shoulder, so a rock rests at the same height either way. On a rough road (issue 136) they do not
agree, and a rock touching the base could rest on it above a rut. So 136 and 145 are most likely
one mechanism, seen where the base and the tile part.

The next test, not yet run: wake a rock in a small stage where the base sits 5 cm above the tile
under it. With the filter in effect the rock falls through to the tile; without it, it rests on
the base. Run it on a pool prim, on a prim made live, and on one made dynamic from the start.

## The stage test (approved by 133; before the run)

A small stage, no road layer: a detail tile (a flat mesh at z 0) and the base (a flat mesh at
z 0.05, in `roadBase`, its members set before play as issue 123 requires), with
`rock_layer.define_groups`' groups. Each rock is one of C6b's prototypes, about 13 cm across,
made as `RockStream._new_prim` makes one, resting on the tile with its lowest point 1 mm above it
(so 4 cm under the base's surface), 1 m from the next. Every rock is woken at the same frame
(its body enabled), then 3 s of physics. Measured: each rock's lowest point at the end, and its
contacts with the base from the contact report.

| rock | made | joins `rocks` | asleep, then woken |
|---|---|---|---|
| D | before play | before play | no: a body from the start |
| D2 | before play | before play | yes |
| P | after play, parked, then reused (the pool's way) | a physics step after it is made | yes |
| L | after play, at rest (a prim made live) | the frame it is made, before any step | yes |
| L2 | after play, collision off | the frame it is made; collision on a frame later | yes |
| N | before play | never (the control) | no |

With the filter in effect a rock stays on the tile, its lowest point near 0. Without it, it meets
the base and is pushed up onto it, its lowest point near 0.05 m.

- **118's prediction.** N rests on the base, about 0.05 m: the test can see a missing filter.
  D and D2 stay on the tile with no base contact. P and L touch the base at once when woken and
  end on it. L2 stays on the tile. The cause is then the order: a rock's collider reaches PhysX
  before its membership of `rocks`, and a membership added to a collider PhysX already holds is
  not applied (issue 123's rule for a group, here for a member). Waking alone is not the cause
  (D2). The fix would be L2's order: a new rock's collision on only after its membership is in.
- If D2 also fails, waking is the cause (its body enabled drops the filter), and L2 fails too.
- **Amended before the run (118, on reading the code again).** P and L were first both written as
  joining `rocks` in the frame they are made. They do not. `reserve` makes the pool's prims at the
  road's load and the ego's spawn, and they join at the next `update`'s flush, after at least one
  physics step. A live prim (`_stream_rocks`) joins in the same `update`, before any step. The
  table above now says so, and the test does that. The prediction for L changes with it: by the
  same reasoning L, whose membership is in before PhysX's first step with it, stays on the tile
  like L2. P still fails. All 46 hits of the diagnosis were pool prims: r2 to r623, within the
  pool's r1 to r768 (`rocks` held 768 members at the first hit).
