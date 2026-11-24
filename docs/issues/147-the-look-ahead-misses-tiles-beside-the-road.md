# 147: the road's look-ahead never asks for the tiles beside the road

**Status:** open (filed by 133 from issue 144's proof). **Severity:** low: speed only. Since
issue 144 the frame's end waits for these tiles, so nothing is missing, but the wait blocks while
the worker makes them. **Found:** 2026-11-24, scensim 118, issue 144's two-pace proof.

## What happens

`RoadLayer._ahead` asks the tile worker for the tiles along each corridor's centreline ahead of a
car, 6 m about it. The collision tiles and the rocks want every tile within 32 m of the car. The
tiles in that circle but off the centreline's band (on Haruna, mostly a column beside the road)
were never asked for. Before issue 144 they were never made at all: on the 1020 m Haruna drive
held to the wall clock, 21 rock tiles (11 rocks, 31.9 to 40.2 m from the car's path) and 21
collision tiles (at least 7.7 m from it). Since issue 144 the frame's end asks for them as they
come within reach and waits while the worker makes them: 48 frames waited over 50 ms, 27 s in all,
on that drive at real time (issue 144's record).

## The fix (proposed, not built)

`_ahead` also asks for every tile within the reach (max of ROCK_REACH and COLLISION_REACH) around
each car that touches a corridor, so the worker has made them before the frame's end needs them.
`Detail.prefetch` skips tiles already made or pending, so asking each substep costs little.

- **118's prediction (before any run).** The same drive as issue 144's proof (Haruna's rocks map,
  10 m/s, 1900 frames, held to the wall clock, probe144) on the fix: frames waiting over 50 ms
  drop from 48 to under 5, their total from 27 s to under 2 s. The (frame, tile) lists stay
  identical to 19ad467's real-time run, since what a frame has is set by the wait, not by when
  the worker began. The unpaced run's rate rises above 19ad467's 33.7 frames a second.
