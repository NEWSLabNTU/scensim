# 160: a COMMANDED body's state reports 0 m/s on CARLA

**Status:** fixed 2026-11-25 (241; numbered by 133). **Severity:** medium: a behaviour model on
CARLA's truth saw its own body at rest, so 092 K13's car follower crawled; K12's walker had the
same state, and nothing read its speed.
**Found:** 2026-11-25, scensim 241, in 092 K13's exit check 2 (attempt 4): on all three runs of
the platoon on Town01 the follower moved at 0.075 m/s, against the 8 m/s its leader drove.

## What happens

The CARLA world server moves a `COMMANDED` body itself (092 K12): before each step it integrates
the body's latest command (`scensim_carla_world`'s `commanded::Body`) and poses the actor with
physics off. CARLA measures an actor posed that way at 0 m/s. Two things report the body:

| Report | Read by | Velocity before the fix |
|---|---|---|
| the apply's read-back (`ApplyReply.read_back`) | SSv2's entity status | the integrator's (since K12) |
| the step's states (`StepReply.states`) | the truth stream, the gap trace, the seats' models | CARLA's: 0 |

The second was missed. A model on the truth stream reads its own body's speed from the states,
so the IDM follower saw v = 0 at every frame and commanded `0 + a dt`, whatever its gap.

Attempt 4's gap trace (`scenarios/projects/k13_platoon/runs/2026-11-25T05-09-29_platoon_town01_
decel-6.0_street-6583_r0/gap_trace/`), the follower at frame 400 of the decel 6 run:

```
"velocity": [0.0, 0.0, 0.0], "velocity_source": "measured", "cmd_frame": 20362
```

while its SSv2 position moved 0.75 m over the 200 frames (10 s) from frame 201 to 401. On all
three runs (decel 2, 4 and 6; 7740, 6914 and 6679 frames) the follower averaged 0.0749 m/s, and
its reported velocity was 0 in every frame.

SSv2's own conditions on the body (a SpeedCondition, say) were not affected: they read the
read-back, which carries the integrator's state.

## The fix

`CarlaBackend::actor_states` reports a commanded body's velocity as its integrator's: the speed
along its yaw (`commanded::Body::velocity`, through `state_velocity`). Every other actor reports
what CARLA measured, as before. Test: `a_commanded_body_reports_its_commanded_speed` (a commanded
walker and a commanded car, each after 100 steps, report the commanded speed along the
commanded heading; a body with no command reports the measured velocity).

The model reads the world's velocity, as designed. A first fix in the model (it took the speed
it last commanded as its own) was withdrawn before it landed: it was open loop, hid the world's
defect, and on seats would ignore anything the world does differently from the command.

`velocity_source` still says `measured` for these bodies. The value is the body's actual
velocity, as this server moves it; a separate label for commanded bodies would be a schema
change and is not part of this fix.

Isaac refuses `COMMANDED` bodies, so it has no counterpart.
