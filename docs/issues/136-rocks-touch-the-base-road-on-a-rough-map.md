# 136: rocks touch the base road on a rough map

**Status:** fixed by issue 145's fix, siw 1535c3b (the rock pool joins `rocks` before the
next physics step). **Severity:** medium until understood: the filter that keeps
the rocks off the base road (issue 123) does not hold for some rocks on a rough road, so a rock
can rest on the base above a rut or a pothole, the thing the filter exists to prevent.
**Found:** 2026-11-24, scensim 118, 086 C6d's live guard.

## What happens

`fixture_cost --follow --guard-ms 10000`, one car, siw 31593ab (scensim main ddf1c32e), on
C6d's *rough_rocks* map (C5d's Haruna, its record with ISO 8608 class C roughness, ruts,
potholes 2 per 100 m, one washboard zone, and C6b's rock cover). Issue 123's self-check found
12 rocks touching the base road within their first second awake: 7 on `/World/env/Road` and
5 on `/World/env/Terrain` (r16, r20, r91, r118, r219, r236, r246, r322, r338, r364, r523,
r547: all prims of the parked pool, whose 768 prims are r1 to r768). The smooth *rocks* map,
with the same cover and the same code, had none in 18 runs (086 C6b). On *rough_none* the guard
passed.

## The diagnosis (before the run)

`fixture_cost` on *rough_rocks* again, with no other load on the host (no gate), and in a
scratch copy logging, for each hit: the rock's index, prim, zone, size and loose or fixed; its
rest height against the base road and the collision tile under it; the time since it woke; the
frame; and from the stage at that moment whether its prim is a member of `rocks` and the
collider of `roadBase`, and what `rocks` filters. The control is the smooth *rocks* map in the
same session.

- **118's prediction.** The hits recur on the quiet run, 8 to 16 of them, and the control has
  none. Of two readings:
  - (a) the group membership: some of those rocks' prims are not in `rocks` when they wake (a
    pool prim's membership dropped and not restored as rocks come and go, which the rough road's
    tiles make more frequent);
  - (b) the membership holds and PhysX still reports the pair;
  118 expects (a), its mechanism not yet known.
- The first frames' largest, on a quiet host, is under 10 s (6 to 9 s).

## The cause and the fix (2026-11-24, from issue 145)

Issue 145 found the mechanism on the smooth map. Every rock woken from the pool met the base,
because `RockStream.reserve` wrote the pool's `rocks` membership a physics step after PhysX took
the prims in, and PhysX fixes a collider's filtering at intake. On the smooth map the base and the
tiles coincide on the shoulder, so it did no harm. Here they part, which is how 136 saw it first.
Reading (a) of the prediction above was right in kind (the membership), not in its mechanism (the
timing, not a dropped membership). The diagnosis planned above was not run; 145's stage test
and the fix's proof replaced it.

The fix (siw 1535c3b) writes the pool's membership before `reserve` returns, and an intake
self-check names any collider left out of its group. This map's run, as 136 found its 12
(`fixture_cost --follow --cars 1 --guard-ms 10000`, to 280.4 m): **0 rocks on the base**, the
guard passing (first frames' largest 182 ms). Record: issue 145's doc, `g136_1535c3b_rough_rocks.*`.

That run reaches s 280.4 m. On the same map, 086 C6d's live runs (1.47 km) still log 10 or 11
base contacts a drive past it: issue 152.
