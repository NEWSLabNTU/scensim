# 142: since issue 134 the road's rocks load about 30 m later along the course

**Status:** open; a probe comes first (133). **Severity:** high until shown otherwise: a rock not
loaded when a wheel reaches it is silently missing from a study on rocks. **Found:** 2026-11-24,
scensim 118, issue 139's bisection.

## What happens

086 C6b's fixtures on fixture_c6b (raycast) count the rocks loaded as the car drives (a running
count, `rock_check`'s `loaded_max`). On siw 637b454 (issue 128's recheck) 80 rocks were loaded by
s 112.9 m; since issue 134 (3a4fcd7, by elimination: 31593ab, 4df3198 and 87591b4 all load the
same) the 80th loads at about s 143 m, and at loose_15's middle 100 against 130. Both reach the
same 253 by the boulder at s 400 m. No tile is dropped by issue 139's queue (0 in a logged run).
Rocks load within ROCK_REACH (32 m) of a car from ready tiles only, so a lag of about 30 m of
travel suggests tiles become ready only as the car nears them. 134 moved the tile's look (its
base and zones) into the worker, which may make each worker tile slower.

The fixtures' own rocks were there when needed (every case's measure equals 128's to the digit);
whether a placed rock near a wheel's path was ever missing is not known.

## The probe (planned, prediction first)

On siw 6c6a044 (before 134) and on main: for each rock, the car's s when it loads against the
rock's own s, and each tile's worker time. The key number is the least lead (the rock's s less
the car's at its load) over the rocks a wheel passes within 1 m of; under the car's stopping
distance at its speed, rocks are being missed.

## The probe as built (before the runs)

C6b's fixtures on fixture_c6b (raycast, the whole set) through a wrapper of `fixture_drive`
(`probe142.py`) that logs every rock tile loaded into the rock data (`RockStream._load`: the
tile, its rocks' positions, the car's position then), the car's position every frame, every tile
the worker made (its key and worker time) and every tile made on the caller's thread instead.
Run on siw 6c6a044 (before 134) and on siw main 56b8e39, GPU0 quiet and the host otherwise idle
(the loading depends on the worker's pace). A rock's lead is its s along the course less the
car's (its rear axle, `fixture_drive`'s origin) when its tile loaded; a rock is in a wheel's path
when it lies within 1 m of a wheel's line (the car's lateral place at the rock's s, plus or minus
half the tread, 0.83 m). The car's stopping distance at 11.1 m/s, braking at 7 m/s^2 after
0.5 s, is about 14 m (5.6 + 8.8).

- **118's prediction:** the worker's time a tile rose with 134 (its look is now made there): at
  least 1.5 times 6c6a044's median. On 6c6a044 every rock in a wheel's path loads at least 25 m
  ahead of the car. On main the least lead over those rocks is under 14 m: rocks are being
  missed in effect, since a wheel can reach one before the car could stop for it. Tiles are made
  on the caller's thread on main and not, or far less, on 6c6a044.
