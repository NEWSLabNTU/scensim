# 161: the world servers take environment values out of range, and read back what they stored

**Status:** open, plan written 2026-11-25 before any code (243; numbered by 133 on 2026-11-25;
after 092 K9f). **Severity:** medium. A world server's read-back is the check behind every knob
and every road condition. On CARLA it can echo an impossible value, or show the value before a
send.
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
   becomes a second guard, not the only one, and scensim judges a `weather:` knob's read-back on
   CARLA again (since issue 171 it is recorded as unverified; `run.apply_knobs`).

The check: 086 C7's `scensim_world_check conformance` on CARLA, rerun by 118, and 092 K9e's
knob runs on CARLA.

## Why CARLA's read-back can predate the send (read, not yet measured)

LibCarla 0.9.16 sends `set_weather_parameters` without waiting for it
(`Client::SetWeatherParameters` is `AsyncCall`, its future discarded) and `get_weather_parameters`
waiting (`CallAndWait`). A read right after the set can be served before the set is. That
would explain issue 171's stale first reply with no tick involved; that CARLA applies the
weather only at a tick would explain it too. Step 0 tells the two apart before anything is
built on either.

## The plan, before any code

One rule in each of the two protocol shells, so that every world server keeps it: the Rust
shell (`scensim_core::world_server`, which the CARLA world server runs on) and the Python shell
(`scensim_world_server`, Isaac's).

0. **Probe first, on CARLA alone** (my CARLA, after 092 K9f-b's Isaac run, never beside Isaac).
   A test binary in `scensim_carla_world` against a synchronous Town01: 200 times, set
   `sun_altitude_angle` to one of two values and read it back (a) at once, (b) once more at
   once, without a tick, (c) after one tick. Written before the run: (c) reads the new value 200
   of 200. If (a) is ever stale and (b) then reads the new value, the cause is the unordered
   send. If (b) stays stale until (c), CARLA applies weather only at a tick. Either way the fix
   below reads after a step. The probe decides only what the doc says about the cause.
1. **Refuse out-of-range values in the shells.** `SetEnvironment`'s weather fields are checked
   against the ranges scensim's knobs use (`knobs.FIELD_RANGES`: `sun_elevation` [-pi/2, pi/2]
   rad, `sun_azimuth` [0, 2 pi) rad, `fog_visual_range` above 0 m, `precipitation_intensity` 0
   or more mm/h, `cloud_cover_oktas` [0, 8]). An out-of-range value refuses the whole request,
   before anything changes, naming the field, the value, the range and its unit, and for an
   angle the value in degrees, as `knobs.field_range_problem` words it. This covers a scenario's
   own `EnvironmentAction`, which SSv2 forwards and scensim does not check. The bridge passes the
   refusal to SSv2 as it passes any.
2. **Read back the sun CARLA shows** (`scenario_weather.rs`, `scenario_sun`): CARLA's altitude
   folded into [-90, 90] deg, the azimuth turned by 180 deg when the fold crosses a pole. The
   other fields already read back what CARLA holds after its own clamps (rain at most 25 mm/h,
   fog, cloud). With 1. in place no SetEnvironment gets there out of range. A value set through
   `set_weather` in CARLA's own parameters (degrees, not checked) still can, and then reads back
   as shown. Written before the test: K9e's 60 rad (3437.7 deg stored) reads back as elevation
   -0.3097 rad, the value Isaac showed for the same send.
3. **Read back after a step.** `StepReply` gains `environment_applied` (`ScenarioWeather`) and
   `road_condition_applied` (`RoadConditionReply`), additive like its other recent fields (no
   protocol bump). Each shell fills one on the first step after a `SetEnvironment` or
   `SetRoadCondition`, from the server's `applied_environment` or `applied_road_condition`,
   called after the simulator's tick returns, when the server declares `ENVIRONMENT_APPLIED` or
   `ROAD_CONDITION_APPLIED`. The replies to the sends stay as they are.
   - The bridge records a reply's value when it arrives. A step's value replaces it, and the
     gap trace's `knob` line and K9f-a's `road_condition` record gain `after_step: true` (absent
     otherwise; truth-stream.md). Issue 171's repeated first send stays, as a second guard.
   - scensim judges a read-back marked `after_step`, whatever the simulator. `run.apply_knobs`
     stops choosing by simulator name, and a CARLA `weather:` knob is judged again.
     `weather_read: unverified` stays for a trace without the mark, from an older bridge or
     server.
4. **Tests.**
   - Each shell refuses each field out of range by name and applies nothing. Each takes the
     bounds themselves.
   - The step after a send carries the read-back taken after the tick. A step with no send
     carries none.
   - `scenario_sun` folds 3437.7 deg to -0.3097 rad.
   - The bridge prefers the step's read-back and marks it.
   - `knobs.compare` judges a marked CARLA weather read-back, and a CARLA trace without the
     mark stays unverified.
   - A conformance check: `scensim_world_check conformance` sends an out-of-range
     `SetEnvironment` and expects the refusal by name. It reads the step after a good one and
     expects the value sent within the tolerance.
5. **Docs**: the proto's comments, truth-stream.md (`after_step`), `scensim_carla_world`'s
   README (the refusal and the sun read-back), this doc's status, and 092 K9's note that a
   CARLA weather knob is judged again.

Landing: `scensim_world_protocol` first, then `scensim_carla_world` and `scensim_isaac_world`
with their `deps/` pins moved to it. scensim's pins last, with the bridge and scensim changes.
Each lands after its own gate, scensim after the full gate on the exact tree. Isaac needs no
code of its own beyond the pin: the Python shell does both parts, and its read-back of the sun
is already the physical one.

The check, after the landing, written before it:

- 086 C7's `scensim_world_check conformance` on CARLA (118's rerun, on the 2010 testbed)
  passes, with the new check.
- 092 K9e's knob runs on CARLA judge the weather knob again, with no false error. Their gap
  traces carry `after_step: true` on every knob read-back after the first frame, and the read-back
  equals the value sent within `knobs.TOLERANCE`.
