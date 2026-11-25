# 161: the world servers take environment values out of range, and read back what they stored

**Status:** fixed in code and tests, 2026-11-25; the probe (step 0) done the same day (the cause:
the unordered send); the live check's two knob runs on CARLA done the same day, as predicted
(below); 118's C7 conformance on CARLA 2010 pending (243; numbered by 133 on 2026-11-25;
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

## Why CARLA's read-back can predate the send (measured: the unordered send)

LibCarla 0.9.16 sends `set_weather_parameters` without waiting for it
(`Client::SetWeatherParameters` is `AsyncCall`, its future discarded) and `get_weather_parameters`
waiting (`CallAndWait`). A read right after the set can be served before the set is. That
would explain issue 171's stale first reply with no tick involved; that CARLA applies the
weather only at a tick would explain it too. Step 0 tells the two apart before anything is
built on either.

**Step 0's result (2026-11-25, 20:01-20:04, my CARLA 0.9.16 alone on RPC 2100, Epic, Town01;
the `carla` wheel 0.9.16, client and server both reporting 0.9.16; synchronous, 0.05 s steps).**
200 sends of `sun_altitude_angle`, alternating 20 and 50 deg (the first equal to the boot sun, 20,
so 199 changed it):

| read | shows the value sent |
|---|---|
| (a) at once | 168 of 200 |
| (b) once more at once, no tick between | 200 of 200 |
| (c) after one tick | 200 of 200, as predicted |

All 32 stale reads in (a) showed exactly the weather before the send, and every one of them read
the new value in (b), with no tick between; none stayed stale until (c). So the cause is the
unordered send: LibCarla's `AsyncCall` for the set lets a `CallAndWait` get right after it be
served first, about one time in six here. CARLA does not wait for a tick to apply the weather.
On exit the probe put CARLA back to asynchronous mode and the boot sun (20 deg); CARLA was
killed by its process group, and its ports were free after. The script and its rows:
`/var/tmp/aeon/k161-probe/` (`probe.py`, `probe.json`).

What it means for the fix: the read after the step (3.) stays sound: after a tick, 200 of 200
showed the send (the set has no reply to wait for; a tick, or here a second round trip, came
after it). Option (i) of the amendment to 3. is now
open: the CARLA world server's `set_weather` could read back until `get_weather` shows the
request (bounded), with no tick, and then a `weather:` knob could be judged at once instead of
after the run. Not done here; a follow-up, if wanted.

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
   *Amended 2026-11-25 (243, with 133's OK, before the first run):* the probe is a Python script
   on CARLA's own Python client, not a Rust test binary: the `carla` wheel 0.9.16 (`pip show
   carla`), whose `client.get_client_version()` and `get_server_version()` it prints and requires
   to be 0.9.16 both. Its `world.set_weather` and `get_weather` go through LibCarla 0.9.16's
   `Client.cpp`, as the CARLA world server's do: its carla-sys build is
   `libcarla_client.0.9.16`, where `Client::SetWeatherParameters` is `AsyncCall` and
   `Client::GetWeatherParameters` `CallAndWait`. My CARLA alone on RPC 2100 (Epic, Town01), the
   card checked first; the probe sets synchronous mode with a fixed step, and restores the
   asynchronous mode and the original weather on exit, on error too (`try/finally`); CARLA is
   killed by pid after. The two values are 20 and 50 deg, alternating, so every send changes
   it. The predictions above are unchanged.
1. **Refuse out-of-range values in the shells.** `SetEnvironment`'s weather fields are checked
   against the ranges scensim's knobs use (`knobs.FIELD_RANGES`: `sun_elevation` [-pi/2, pi/2]
   rad, `sun_azimuth` [0, 2 pi) rad, `fog_visual_range` above 0 m, `precipitation_intensity` 0
   or more mm/h, `cloud_cover_oktas` [0, 8]). An out-of-range value refuses the whole request,
   before anything changes, naming the field, the value with its unit, and the range with its
   unit. For an angle it also gives what the number would be read as degrees, the K9e lapse:
   `sun_elevation 60 rad is outside [-1.5708, 1.5708] rad (60 deg would be 1.0472 rad)`.
   Every message names a unit, rad or deg as the field is. This covers a scenario's
   own `EnvironmentAction`, which SSv2 forwards and scensim does not check. The bridge passes the
   refusal to SSv2 as it passes any.
   *Amended 2026-11-25 (243, found writing the shells, before any run):* cloud cover takes 0 to
   9 oktas in the shells, not 0 to 8. The protocol defines 9 as "the sky cannot be seen"
   (`ScenarioWeather.CloudCover`), so a scenario may send it. scensim's knobs keep [0, 8], their
   own narrower choice. 133 accepted the shells' 0 to 9 the same day (OpenSCENARIO's
   `fractionalCloudCover` has `nineOktas`).
2. **Read back the sun CARLA shows** (`scenario_weather.rs`, `scenario_sun`): CARLA's altitude
   folded into [-90, 90] deg, the azimuth turned by 180 deg when the fold crosses a pole. The
   other fields already read back what CARLA holds after its own clamps (rain at most 25 mm/h,
   fog, cloud). With 1. in place no SetEnvironment gets there out of range. A value set through
   `set_weather` in CARLA's own parameters (degrees, not checked) still can, and then reads back
   as shown. Written before the test: K9e's 60 rad (3437.7 deg stored) reads back as elevation
   -0.3097 rad, the value Isaac showed for the same send.
3. **Read back after a step.** A new capability, `CAPABILITY_READBACK_AFTER_STEP = 15` (133's
   choice, 2026-11-25, the protocol's pattern), needing `ENVIRONMENT_APPLIED` or
   `ROAD_CONDITION_APPLIED`. `StepReply` gains `environment_applied` (`ScenarioWeather`) and
   `road_condition_applied` (`RoadConditionReply`), additive (no protocol bump). On a server
   declaring the bit, the shell fills one on the first step after a `SetEnvironment` or
   `SetRoadCondition`, from the server's `applied_environment` or `applied_road_condition`,
   called after the simulator's tick returns. The replies to the sends stay as they are.
   Both world servers declare the bit.
   - A server that declares the bit and leaves the field empty on the step after a send is a
     protocol error, named by the bridge (the capability, the field, the frame), never a
     silent fallback to the reply's value.
   - The bridge records a reply's value when it arrives. A step's value replaces it, and the
     gap trace's `knob` line and K9f-a's `road_condition` record gain `after_step: true` (absent
     otherwise; truth-stream.md). Issue 171's repeated first send stays, as a second guard.
   - scensim judges a read-back marked `after_step`, whatever the simulator. `run.apply_knobs`
     stops choosing by simulator name, and a CARLA `weather:` knob is judged again.
     `weather_read: unverified` stays for a trace without the mark, from a server without the
     bit.

   *Amended 2026-11-25 (243, found writing the scensim part; 133's choice (ii) the same day;
   before any of its code):* the paragraph above does not reach a `weather:` knob. The run sends
   it through the bridge's `set_weather` before the scenario starts and reads it back at once
   with `get_weather`, with no step between, so `READBACK_AFTER_STEP` (`SetEnvironment` and
   `SetRoadCondition` only) never covers it; the `after_step` mark reaches only the gap trace's
   knob lines (profiles and static `environment:` values), which issue 171's repeat already
   judges on CARLA. So:
   - a `weather:` knob is judged from a `get_weather` at the run's end, while the world server is
     still up and before the stack stops, hundreds of ticks after the send (the world server keeps
     the weather; a scenario `EnvironmentAction` that sets weather beside a weather knob is
     already refused). The record and the verdict call it the read "after the run", never
     "applied before frame 0";
   - the immediate read-back stays in the record, unjudged on CARLA, as now;
   - an end read that fails (the stack gone, a time-out) leaves the knob `unverified`, not an
     error;
   - tests: a fake bridge whose immediate read is stale and whose end read is right judges ok;
     one whose end read is wrong judges `knob_mismatch`; one whose end read fails is
     `unverified`.
   The probe (step 0) stays, for the doc's cause only. If it shows the unordered send, the CARLA
   world server's `set_weather` could wait until `get_weather` shows the request (bounded),
   and an immediate judgement could replace this one later.
4. **Tests.**
   - Each shell refuses each field out of range by name and applies nothing. Each takes the
     bounds themselves. Every refusal message names the unit.
   - The K9e case (133, 2026-11-25), so the units lapse cannot come back: 60 sent as a degrees
     field (CARLA's `sun_altitude_angle` by `set_weather` parameters) is accepted, and 60 sent
     as `sun_elevation` (rad) by `SetEnvironment` is refused, the message saying rad and giving
     60 deg as 1.0472 rad.
   - The step after a send carries the read-back taken after the tick. A step with no send
     carries none.
   - `scenario_sun` folds 3437.7 deg to -0.3097 rad.
   - The bridge prefers the step's read-back and marks it. A server declaring the bit that
     leaves the field empty after a send is refused by name.
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
Each lands after its own gate, scensim after the full gate on the exact tree, and each push
after 133's OK. Isaac's own code is one line, declaring the bit: the Python shell does the
rest, and its read-back of the sun is already the physical one.

Order (133, 2026-11-25): 092 K9f-b lands first, then this issue, then K9f-a's code, whose
`road_condition` record then carries `after_step` from its start (K9f-a's plan amended to say
so, labelled and dated).

**Open follow-up, not in 161 (133, 2026-11-25): the knobs refuse 9 oktas while the protocol
takes it.** scensim's `knobs.FIELD_RANGES` gives `cloud_cover_oktas` [0, 8], so a knob cannot ask
for the sky that cannot be seen, which a scenario's own `EnvironmentAction` can. What each world
server does with 9 today, read from the code (nothing run):

- CARLA (`scenario_weather.rs`, `Sky::with`): `oktas.min(8)`, so 9 is shown as 8, `cloudiness`
  100. Its read-back (`Sky::read_back`) gives `cloudiness / 100 x 8`, rounded: 8. A 9 sent reads
  back as 8.
- Isaac (`sky.py`): 9 is kept (`min(9, ...)`) and turns the sun light off (8 dims it by 80 %;
  Isaac draws no clouds). Its read-back (`sky.read_back`) has no cloud cover: Isaac keeps no
  cloud state of its own, so none is read back, whatever was sent.

No read-back of 9 reaches scensim's judging today, nor after 161 (133, 2026-11-25, on the code):
a scenario's own `EnvironmentAction` is never judged (the bridge's `update_environment` drops its
reply; only the knobs' sends are recorded and, with 161, marked `after_step`); a knob cannot send
9 (`FIELD_RANGES`) nor share cloud cover with the scenario's Weather element (two writers are
refused); and a cloud knob is refused on Isaac. 161 pins each with a test: (a) in the bridge, a
scenario's own `SetEnvironment` read-back, the reply's and the step's, is not recorded; (b) and
(c) in `test_knobs.py`. **Widening the knobs to 9 needs:** CARLA's 9 judged as shown, 8, and
labelled so; Isaac's clouds left unjudged, as now.

The check, after the landing, written before it:

- 086 C7's `scensim_world_check conformance` on CARLA (118's rerun, on the 2010 testbed)
  passes, with the new check.
- 092 K9e's knob runs on CARLA judge the weather knob again, with no false error. Their gap
  traces carry `after_step: true` on every knob read-back after the first frame, and the read-back
  equals the value sent within `knobs.TOLERANCE`.

  *Amended 2026-11-25 (243, with the amendment above, before any run):* a frame that sends
  takes the send's own reply, unmarked, and the next step's read-back marks it: a static value
  is sent at frames 1 and 2 (issue 171), so its lines carry `after_step: true` from frame 3 on.
  A `weather:` knob on CARLA is judged from the read after the run: ok, with the read labelled
  "after the run".

**The live check's two runs, predicted before either (2026-11-25, 243; (b) added with 133's
OK).** scensim main 8ad9f151 built from a clean environment (acb, then scensim) in its own
worktree; my CARLA 0.9.16 alone on RPC 2100 (Epic, booted on Town01), the card checked first;
each run on its own fresh stack. For each, the bridge's and the CARLA world server's install
binaries are newer than the build's start, and the live processes' `/proc/<pid>/exe` are those
files.

- **(a) k9_cs3, `cs3_stale_map.xosc`, pm=current** (K9e step 2a again; its `illumination` knob is
  the static `environment: {sun_elevation: 1.0472 rad}`). SSv2: the ego stops before the
  barriers and the run fails, exitFailure at 240 s, as step 2a had it. `knobs` ok; no protocol
  error. The gap trace's `illumination.sun_elevation` knob lines: sent at frames 1 and 2,
  `after_step: true` from frame 3 on, on every line after, and every marked read-back 1.0472 rad
  within the knob's tolerance (0.0011047 rad).
- **(b) the same run on a scratch copy outside the repository whose `illumination` knob is a
  `weather:` value** (the only live path to the read after the run; no project in the repository
  has a `weather:` knob). The copy is `/var/tmp/aeon/k161-live/k9_cs3_w/`, k9_cs3 at 8ad9f151
  with one line changed in `testbench.yaml`:

      -    illumination: {values: {day: {environment: {sun_elevation: 1.0471975511965976}}}, default: day}
      +    illumination: {values: {day: {weather: {sun_altitude_angle: 60}}}, default: day}

  (the copy's `testbench.yaml` sha256 0c7d70cb1ae2e95c33dfd8496d20fab7e41275ba28d896d6a656b218dc641e42;
  the sha256 of the sorted list of its files' sha256s
  73bde034447ecc1c2c54c0b352ec447e9ca7b785c9ad1219c47a2244b1e168f5). SSv2 as in (a).
  `result.json`'s `knobs`: `weather_read` "after the run"; `weather_after_run.read.sun_altitude_angle`
  60 deg (`set_weather`'s unit, CARLA's own) within 1e-3, `off` empty; the knob ok; no
  `knob_mismatch`. The read right after the send may be stale (about one time in six, by the
  probe), and then it is listed under `weather_read_off`, which fails nothing.

**The live check's two runs, the result (2026-11-25, 20:45-20:57, 243).** Both as predicted.
Built: scensim main 8ad9f151 in `/var/tmp/aeon/wt-161p` from a clean environment, acb from
20:06:21, scensim to 20:29:55; the bridge's install binary 20:23:57, the CARLA world server's
20:27:58. My CARLA 0.9.16 alone on RPC 2100 (Epic, Town01, 6185 MiB free on the card at the
start; RPC up at 20:45:23); each run on its own stack, stopped after it. The live processes'
`/proc/<pid>/exe` were those install files for the bridge and the CARLA world server in both
runs; `acb_bridge` ran acb's own workspace copy
(`src/autoware_carla_bridge/install/acb_bridge/...`), built in the same clean build. After both,
CARLA's process group was gone and its ports free.

- **(a)** `2026-11-25T20-46-15_cs3_stale_map_pm-current_barrier_lane-6583_r0`: failed, exitFailure
  at 240 s (the `limit` condition), no error. `knobs` ok: `illumination.sun_elevation` sent 2
  times, 5018 frames, 5017 judged, none unread, `off_frames` empty, largest deviation 0.0 against
  the 0.0011047 rad tolerance, read back 1.0471975511965976 rad. The truth (schema 3): knob lines
  at frames 1 and 2 `sent: true` with no `after_step`, every line from frame 3 on `after_step:
  true`, each read-back 1.0471975511965976.
- **(b)** `2026-11-25T20-51-54_cs3_stale_map_pm-current_barrier_lane-6583_r0`, on the scratch copy:
  failed, exitFailure at 240 s, no error. `knobs` ok: `weather_read` "after the run",
  `weather_after_run.read.sun_altitude_angle` 60.0, `off` empty, the knob's `applied` and
  `applied_after_run` both 60.0; no `weather_read_off` (the read right after the send was not
  stale this time), no `knob_mismatch`. The copy that ran is the one predicted:
  `testbench.yaml` sha256 0c7d70cb...; the tree hash 73bde034... as before, which is (correcting
  its description above) the sha256 of `sha256sum`'s lines over the copy's files in sorted order,
  names included, taken without `assets/` (fetched after) and without
  `state/Town01/traffic_lights.yaml`, which the run itself wrote.
