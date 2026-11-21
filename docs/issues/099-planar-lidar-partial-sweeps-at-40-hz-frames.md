# 099: a lidar profiled faster than the stock variant's 20 Hz tick publishes tails of revolutions

**Severity**: medium. The RoboRacer's 40 Hz planar lidar under 40 Hz frames published scans with a
third of the beams missing. A missing beam reads `inf`, which means nothing in range, so a wall
follower steered into the wall it could not see (W20's first runs). **Status**: open; the
mechanism is found, and aib's fix is checked against the references before it lands. **Found**:
2026-11-21, scensim 241, roadmap 091 W20, on Isaac Sim 6.2, with both of 241's GPUs held at 95 to
100 % by another user's jobs.

## What happens

The setup is the RoboRacer example car's UST-10LX class lidar on `/scan`: 270 deg, 1081 beams,
40 Hz, 10 m, a 1440-column profile (W19). aib's runner drives it at 240 Hz physics, rendering
pinned to GPU 0, in a 12 m x 8 m walled room where every beam has a wall in range. Each run lasts
30 s.

| frames | the lidar's tick | `/scan` | beams in range |
|---|---|---|---|
| 40 Hz | 20 Hz (as shipped) | 33.1 Hz | 68.5 % |
| 40 Hz | 40 Hz | 39.8 Hz | 91.0 % |
| 20 Hz | 20 Hz (as shipped) | 20.0 Hz | 91.1 % |
| 20 Hz | 40 Hz | 20.0 Hz | 91.1 % |

91 % is a whole scan here: the other beams reach past the scanner's 10 m into the room's far
corners, or are single beams without a return. Sixty raw reads from the RTX annotator at 40 Hz frames, tick 20, were dumped. The
whole ones start at azimuth 0 and span 24.98 ms, a turn. The bad ones are contiguous tails of a
turn: they start at 60, 120, 180, 240 or 300 deg and end at 0 deg, spanning 4.2 to 20.8 ms, and
their points' times agree with their azimuths. aib's `ScanGate` published each read whose first
point was new, so every tail went out as a scan.

Once, at 20 Hz frames, a 120 s run on f1tenth_system `humble-devel` had sparse scans from the
first (840 points against about 1210, 44 % of beams in range), and the car drove into a wall
within 2 m. The other runs at 20 Hz frames, both branches, had whole scans throughout.

## Why

aib builds every profiled lidar on Isaac's stock OS1 variant (`OS1_REV7_128ch20hz1024res`) and
sets its firing pattern from the profile, `omni:sensor:Core:scanRateBaseHz` among it, but not
`omni:sensor:tickRate`. The variant authors a tick rate of 20 Hz, with
`omni:sensor:Core:accumulateOutputs` on. Isaac 6.2's own RTX lidar wrapper warns when the tick
rate does not match `scanRateBaseHz`. The sensor renders at its tick rate and accumulates a
revolution across ticks. A profile turning slower than its tick (the shipped 10 Hz lidars on 20)
comes whole, since each turn is assembled over two ticks. A profile turning faster (40 Hz on 20)
handed the annotator tails of turns under 40 Hz frames.

## Fix

In aib: every profiled lidar ticks at its profile's scan rate (`lidar_profile.tick_rate`, set
with the firing pattern). This moves the shipped 10 Hz lidars from a 20 Hz tick to 10 Hz, so
before it lands the Model 3's Autoware lane on Isaac and the T3 Isaac suites are run against
their references; a reference that moves is reported, not adjusted. Then the RoboRacer's cases
at 40 Hz and 20 Hz frames run again, several `humble-devel` starts among them, counting tail
reads. A guard that drops and counts tails comes only if any remain.

A first guard, which judged a read by its points' time span against their azimuth extent and
phases, was not landed. The tails' times agree with their azimuths, so it caught none of them.

Until the fix lands, W20 runs at 20 Hz frames, where `/scan` comes at 20 Hz, half the real
scanner's rate. The guide's RoboRacer section says so.
