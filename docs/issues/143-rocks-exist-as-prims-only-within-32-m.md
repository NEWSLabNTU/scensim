# 143: the road's rocks exist as prims only within 32 m of a car, short of a stopping distance

**Status:** open, a record; the decision (prims further out, or rock data only) comes with 086
C6d's spec (133). **Severity:** medium: it caps what a sensor can see of rocks and biases any
study that avoids one. **Found:** 2026-11-24, scensim 118, issue 142's bar.

## What it is

`RockStream` makes a rock's prim (what PhysX collides with and what the sensors render) only for
the tiles within ROCK_REACH (32 m) of a car that have collision tiles (COLLISION_REACH, 32 m).
A rock further out does not exist for the lidar or the cameras, whatever their range.

Autoware's emergency stop decelerates at 2.5 m/s^2 (the MRM operator's `target_acceleration`).
A stopping distance with a second of reaction and 10 m to spare, v^2 / 2a + v x 1 s + 10 m, is
62.5 m at haruna_down's 50 km/h and 82.2 m at the course's 60 km/h: twice and more the 32 m.

## What it affects

- 086 C6d's detection-range measurement for rocks: capped at 32 m by the world, not the sensor.
- Any study in which the ego should avoid or stop for a rock: it cannot see one in time at
  these speeds.
- Not the wheels: issue 142 holds the physics side (a rock's prim and collider exist before a
  wheel reaches it).
