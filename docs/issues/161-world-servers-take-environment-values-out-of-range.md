# 161: the world servers take environment values out of range, and read back what they stored

**Status:** open (243; numbered by 133 on 2026-11-25; after 092 K9f). **Severity:** medium. A
world server's read-back is the check behind every knob and every road condition. On CARLA it
can echo an impossible value, or show the value before a send.
**Found:** 2026-11-25, scensim 243, in 092 K9e. A knob sent `sun_elevation` 60 (meant as
degrees, in a radians field). The CARLA world server set `sun_altitude_angle` to 3437.7 deg and
read back 60.000001 rad, which passed. Issue 171 then found a read-back taken before CARLA had
ticked.

## What happens

- **Out-of-range values are applied.** `SetEnvironment` takes any number for its fields. The
  CARLA world server converts an angle to CARLA's degrees and stores it as given, so a sun at
  3437.7 deg altitude was set. Isaac's placed its sun along the direction 60 rad gives, and read
  back the physical elevation, -0.3097 rad. Since 092 K9e, scensim's knobs refuse such a value in
  `testbench check` and the run (`knobs.FIELD_RANGES`). A scenario's own `EnvironmentAction`,
  which SSv2 forwards, is not checked there.
- **The CARLA read-back echoes what was stored.** The CARLA world server's read-back converts
  CARLA's stored weather back to OpenSCENARIO's units, so a value CARLA keeps but cannot show
  reads back as applied.
- **The CARLA read-back can predate the tick (issue 171).** `EnvironmentReply`, `set_weather`'s
  reply and 086 C7's `RoadConditionReply` are read right after the send. CARLA 0.9.16's
  `get_weather` can return the previous weather until it ticks.

## The fix wanted

In the world servers, CARLA's first and then Isaac's where it applies:

1. Validate `SetEnvironment`'s fields against their ranges (`sun_elevation` [-pi/2, pi/2] rad,
   `sun_azimuth` [0, 2 pi) rad, `fog_visual_range` above 0 m, `precipitation_intensity` 0 or
   more mm/h, `cloud_cover_oktas` [0, 8]), refusing by name with the unit, as scensim's knobs do.
2. Read back the physical value, the angle CARLA shows, not the number stored.
3. Report each read-back after CARLA has ticked (issue 171's deeper fix). The value the server
   will apply was the other option. 118 prefers the post-tick read: a stuck or refused apply
   would otherwise read back as applied. Issue 171's repeated first send in the bridge then
   becomes a second guard, not the only one.

The check: 086 C7's `scensim_world_check conformance` on CARLA, rerun by 118, and 092 K9e's
knob runs on CARLA.
