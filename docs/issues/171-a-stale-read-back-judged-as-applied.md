# 171: a read-back taken right after a send is judged as what the world applied

**Status:** open (243; numbered by 133). **Severity:** medium. A run's knob judgement can
report a value the world shows as off, or one it does not show as applied, depending on whether
CARLA ticked between the send and the read. Found as a false error run, and K9e's CARLA results
stand. A false pass is also possible when the stale value happens to equal the one sent.
**Found:** 2026-11-25, scensim 243, in 092 K9f-b's CARLA exit suite on main ec592085: the third
run on one stack, `cs3_layout` closure=none, was a `knob_profile` error run.
`illumination.sun_elevation` was read back 0.3491 rad (20 deg) against 1.0472 sent, on all
2023 frames after the send.

## What happens

092 K9e's `environment:` form sends a static knob value once, as a knob profile held constant
from time 0. The bridge sends it through `SetEnvironment` and records the world's
`EnvironmentReply` on every frame's `knob` line until the next send. A constant has no next send,
so its one reply is carried onto every frame. `knobs._static_summary` judged every frame after
the send against that reply. The knob-profile summary never judges a first send's read-back:
its docstring says one taken right after a send "may still show the send before it (CARLA
applies a weather at its next tick)". The static judgement did not follow it.

On CARLA 0.9.16 the reply can be stale:

- **The world server writes only the knob's value.** That stack's world-server log has one
  weather write per run, each the knob's sun at 60 deg.
- **Town01's boot sun is 20 deg.** Its boot weather has `sun_altitude_angle` 20.0, azimuth 275,
  wetness 80 and deposits 40. The CARLA world server puts it back at each `Initialize`
  (`weather_before_scenario`).
- **CARLA can return the previous weather before a tick.** A probe on CARLA 0.9.16 in
  synchronous mode (`/var/tmp/aeon/k9f-probe/`, 2026-11-25): `get_weather` right after
  `set_weather` returned the previous value in 2 of 6 reads, and the new one after a tick every
  time. "Put back 20, then set 60, no tick" read 20.

So run 3's reply showed the 20 deg that `Initialize` had just put back, and the run was judged
off. The world most likely showed 60 deg from its next tick. K9e's CARLA runs (step 2a again,
and K9f-b's first two runs) also judged a single reply. It happened to be fresh: those
conclusions hold, but that judgement could not have caught a lag (K9e's record says so).

## Other read-backs of the same kind

Each is a single reply taken right after a send, with no tick between, on CARLA 0.9.16:

- **A static `weather:` knob** (`run.apply_knobs`): `set_weather` through the bridge, whose
  CARLA world server replies with `self.weather()` read at once, then `get_weather`, before SSv2
  starts. Through a suite the world server stays owned and in synchronous mode (that stack's
  log: one release, after its last run), so nothing ticks between the set and the read. A
  re-read would not help.
- **086 C7's `RoadConditionReply`** (`CarlaBackend::applied_road_condition`): the weather's wet
  look and the ego's tyre friction, read right after `update_environment` applies them. No
  scensim judgement reads it yet (092 K9f-a will), so nothing is misjudged today. Told to 118,
  who owns C7.

Isaac's world server writes its renderer settings and sun light when asked, and its read-back
(`world.applied_environment`) reads those same settings back, so no tick lies between. No lag of
this kind is known there.

## Fix

In the bridge and `knobs`: the bridge's knob profiles repeat a profile's first send on the next
frame. That second send's reply is read after at least one tick. The static summary judges every
frame from the second send's read-back on, and records the first, as the profile summary does.
A constant never read back after its repeat is not ok ("unread after its send"). Every profile
gains one send. This makes the knob judgement sound. The weather knobs' path and C7's reply are
listed above and not changed here.

**The deeper fix belongs in the CARLA world server, and is folded into issue 161.** Issue 161
already has the server validate the environment's ranges and read back the physical value. It
now also takes this: a read-back the server reports after CARLA has ticked, or the value it will
apply, for `EnvironmentReply`, `set_weather`'s reply and `RoadConditionReply`. Then no client has
to know about the tick.
