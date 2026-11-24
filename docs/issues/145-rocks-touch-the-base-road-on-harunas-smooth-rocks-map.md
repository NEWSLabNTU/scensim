# 145: rocks touch the base road on Haruna's smooth rocks map

**Status:** fixed, siw 1535c3b: the rock pool joins `rocks` before the next physics step,
and an intake self-check. **Severity:** medium: issue 123's self-check fires, so
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
- **Run 1 void (2026-11-24 13:17, recorded before run 2).** All six rocks, the control N included,
  ended on the tile (lowest point -2.4 mm) with no base contact. The base was a flat one-sided
  mesh, and a rock that starts under its surface is never pushed up through it. So the test could
  not see a missing filter, and run 1 says nothing about D to L2. For run 2 the base is a solid
  box whose top is at 0.05 m. The cases and the prediction are unchanged. Run 1's log also has
  omni.physx's warning "Collisions are supported currently only in one collision group", and
  run 2 lists every group's members to find which collider it means.
- **133's question, and 118's prediction for it (before run 2).** omni.physx's warning means a
  collider in two collision groups, of which PhysX keeps one. If a rock kept a group without the
  `roadBase` filter, it would collide with the base exactly as measured. Is a pool prim already in
  another group when it wakes? Run 2 lists every group's members before play and at the wake
  frame, each rock's groups by its path or an ancestor's, and a line before each event's physics
  step, so the warnings fall between them in the log.
  - In the stage, nothing but `rocks` lists a rock (aib's `chassis` and `groundQuery` list the
    car's colliders, and there is no car; `roadBase` lists the base; `rockTiles` and
    `roadDetail` list tiles, and there are none). 118 predicts every rock in `rocks` only, at both
    listings. If the warning comes again, it does not name a second group for a rock; 118 expects it
    near the pool prim's late join (frame 11), from omni.physx taking an includes edit on a
    collider it already holds.
  - In the drive, a rock prim's path is under `/World/RoadRocks`, which no other group lists. The
    tiles' static rock meshes (`/World/RoadRocks/s_*`) are in `rockTiles`, not `rocks`. So 118
    does not expect a second group there either. Run 2 tests the stage only. If it shows a rock
    in a second group, the drive's groups get the same listing next.

### The stage test's result (2026-11-24, run 2)

siw main 77075e3, aib 4e8d684, GPU0 under the quiet rule; record `stage145.py`, `run145s.sh`,
`s145.jsonl`, `s145.log` (run 1's as `s145_void1.*`). The control works: N, in no group, was pushed
up onto the base.

| rock | lowest point at the end | base contacts | verdict |
|---|---|---|---|
| D (made before play, a body from the start) | -2.4 mm | 0 | on the tile |
| D2 (made before play, asleep, woken) | -2.4 mm | 0 | on the tile |
| P (the pool's way: made after play, joins `rocks` a step later) | 47.6 mm | 24, from the wake frame (30) | on the base |
| L (made live, joins before any step) | -2.4 mm | 0 | on the tile |
| L2 (made with collision off, on a frame after joining) | -2.4 mm | 0 | on the tile |
| N (the control, no group) | 47.6 mm | 22, from frame 0 | on the base |

**118's prediction (as amended before the run): held, every case.** Only P, the pool's prim,
meets the base. It does so the frame it wakes, and it ends on the base, as the drive's 46 did.

**133's second-group question: no second group in USD.** At both listings, before play and at
the wake frame, every rock is in `rocks` only. No other group lists a rock or an ancestor of one;
`roadBase` lists the base alone. omni.physx's warning came again, once ("Collisions are supported
currently only in one collision group", after omni.fabric's "attribute
collection:colliders:includes not found for path .../rocks"). Its place among the frames cannot
be read from this log: Kit's lines and the script's are separate streams, and the whole run of
210 steps took under a second. It is not explained and stays open.

**The cause.** A rock's collider that PhysX takes in before the rock is in `rocks` keeps no
filter against `roadBase`, even after the membership is added. That holds while the collider is
disabled too (P was parked with collision off in the frame it was made). Waking is not the cause:
D2 and L wake and keep their filter. In the world server and the drives, `RockStream.reserve`
makes the pool's prims at the road's load and at each ego's spawn, and their membership is
written at the next `update`'s `_flush_groups`, after at least one physics step. So every pool
prim is unfiltered, and the pool is where nearly every woken rock comes from. Issue 123's rule
for groups ("made while the simulation runs, not applied to colliders PhysX already holds")
holds for a member too.

**The fix to propose (not built):** `reserve` writes its prims' membership of `rocks` before it
returns, before the next physics step, as a live prim's is (L's order). Its proof: the stage
test's P made that way stays on the tile, and the Haruna drive at 10 and 13.9 m/s gives 0 base
contacts over the course. On the rough map (issue 136) the same should end its 12.

## The rule, a second time: membership before intake (133)

Issue 123 found PhysX applying no group to ground it took in before `roadBase` existed. Here PhysX
applies no `rocks` membership to a rock it took in before the membership was written. One rule,
met twice: **PhysX fixes a collider's filtering when it takes the collider in, and a group
membership written afterwards is ignored.** A collider's membership must be in the stage before the
first physics step that sees the collider.

A third measure of the rule came with the fix's orders (C, below; 133 asked that it stand here):
**a membership naming a path that does not exist yet is not applied when the prim arrives.**
Writing a group's includes ahead of the prims does not help. The membership has to be written
after the prim exists and before the step that takes it in.

History matters here. Issue 123 first made the pool's membership one edit at the road's load, which
logged 769 "only in one collision group" warnings. It then moved that edit a frame later, "as a
live rock does", which ended the warnings. That later edit is what leaves every pool prim
unfiltered. (Issue 123's diagnosis could not see it, because its base was then unfiltered for
another reason, the groups made after play.)

## The fix's order (before the runs)

The pool's membership has to be in before intake, without bringing back issue 123's 769
warnings. Four orders, each in its own process on the stage (`stage145b.py`): 64 pool prims made
after play and parked, then reused over the base box and woken. Read for each: the woken prims'
base contacts and end heights, and omni.physx's "only in one collision group" warnings.

| order | how the pool is made |
|---|---|
| A (today) | made and parked; `rocks` includes written a physics step later, in one edit |
| B | made and parked; `rocks` includes written in the same frame, one edit, before any step |
| C | `rocks` includes written first, naming paths not yet defined; then the prims made and parked, all before any step |
| D | as A, plus each prim's own `UsdPhysics.FilteredPairsAPI` naming the base, written as it is made |

- **118's prediction.** A: all 64 meet the base, with 1 warning at most. B: none meet it, with
  about 63 warnings, issue 123's "each collider added after the first" (so B's filter holds
  despite its warnings, as the stage's L did). C: none meet it; the warning count is unknown to
  118. D: none meet it, with 1 warning at most. The fix takes D's or C's order, whichever holds
  with no warnings: D, if both. D's filter is the rock's own and needs no group timing. The
  `rocks` membership stays, for `groundQuery`.
- **Amended before the runs (118).** D cannot be the fix alone. `rocks` filters `groundQuery` as
  well as `roadBase`, and a pool prim taken in before it joins `rocks` lacks both filters, so
  the wheels' ground query may also take a rock for ground (not yet measured). A pair filter
  for the base mends one of the two. The fix needs the membership in before intake, B's or C's
  order. D stays in the runs, as a measure of the pair filter alone.

### The orders' result (2026-11-24, 15:11; GPU0 held by another user's job from 14:02)

siw 77075e3 code, `stage145b.py`, `run145b.sh`, `s145b.jsonl`, `s145b_{A,B,C,D}.log`.

| order | pool prims meeting the base | ending on the base | "only in one collision group" |
|---|---|---|---|
| A (today: membership a step later) | 64 of 64 | 64 | 0 |
| B (membership in the same frame, one edit) | 0 | 0 | 0 |
| C (includes written before the prims exist) | 64 of 64 | 64 | 0 |
| D (A plus a pair filter to the base) | 0 | 0 | 0 |

Each run also logged omni.fabric's "includes not found for path .../rocks" once.

**118's prediction, as measured:**

- A: held.
- B: held on the contact (none meet the base), failed on the warnings: 0, not about 63.
- C: failed. A membership naming paths not yet in the stage is not applied when the prims
  arrive, so C is the same as A.
- D: held. The pair filter keeps a pool rock off the base, but not off `groundQuery` (amended
  before the runs).

**The fix takes B's order**, as built: `reserve` writes the pool's membership before it returns
(siw branch `issue-145`). Issue 123's 769 warnings for that order did not come in the stage. Whether
they come in a drive is read in the proof runs below.

## The fix's proof (siw issue-145 1535c3b; before the runs)

The stage's B is P made the fix's way: 0 of 64 met the base. Then, on 1535c3b, under the quiet
rule:

1. The Haruna drive as the diagnosis (probe145, one car, 1900 frames, paced to real time), at
   10 and 13.9 m/s.
2. Issue 136's own run on *rough_rocks*: `fixture_cost --follow --cars 1 --guard-ms 10000`, as
   136 found its 12 (400 timed frames, to about 280 m), like for like.

- **118's prediction.**
  - (1): 0 base contacts at both speeds, where 77075e3 had 9 and 37. The rocks woken are about as
    before (9 and 37 first wakes), since waking does not change. Issue 145's intake WARN: 0. The
    "only in one collision group" warning: at most 1, as before. Issue 123's 769 do not come
    back, as in the stage's B.
  - (2): 0 rocks on the base, where 136 had 12. The guard passes, unless a first frame takes
    over 10 s (136 measured 10.4 s on a loaded host; this host is quiet before each start).

### The fix's proof: result (2026-11-24, 15:22 to 15:27)

siw issue-145 1535c3b, aib 4e8d684, GPU0 under the quiet rule; record `run145p.sh`,
`f145_1535c3b_v10.*`, `f145_1535c3b_v139.*`, `g136_1535c3b_rough_rocks.*`.

| run | 77075e3 | 1535c3b | first wakes | intake WARN | "one collision group" |
|---|---|---|---|---|---|
| Haruna, 10 m/s, 1020 m | 9 | **0** | 9 | 0 | 1 |
| Haruna, 13.9 m/s, 1329.8 m | 37 | **0** | 34 (and 19 wakes again) | 0 | 1 |
| 136's run, *rough_rocks*, 280.4 m | 12 (31593ab) | **0** | (not probed) | 0 | 1 |

**118's prediction: held.** 0 base contacts in all three. The intake self-check found nothing.
The warning came once a run, as before the fix, and issue 123's 769 did not come back. 136's guard
passes (first frames' largest 182 ms, base contacts 0). The rocks woken are about as before: 9, and
34 against 37 at 13.9 m/s, a start-sensitive count (issue 141). Each log still ends on the tile
worker's `BrokenPipeError` at exit (issue 139's follow-up).

**Status:** fixed by the pool's order. Issue 136's 12 on the rough map are the same mechanism
and go to 0 with it. 136's own doc records that, and C6d's runs are no longer blocked by it.
