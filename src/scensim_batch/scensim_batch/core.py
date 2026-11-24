"""One batch's step, independent of the physics engine (roadmap 092 K2.2; batch-executor.md
section 4): the ego through its control component and a physics backend, SSv2's default
vehicles through scensim_batch.npc, props where Init put them, all slots at once.

    run = BatchRun(compiled, world, backend, component)
    run.reset()                       # every slot to its record
    obs = run.step(commands, dt)      # the ego's commands, a dict of [N] arrays (S3's form)

The backend is the engine: Isaac Lab's PhysX vehicle in the environment (K2.2's env), a
kinematic stand-in in tests. Its contract:

- `reset(mask, x, y, yaw, speed)`: slots `mask` [N] to those poses and speeds ([N] each);
- `apply(actuation)`: the component's actuation (S3: drive, brake [N, 4], tire_angle [N]);
- `advance(dt)`: one physics step;
- `state()`: {x, y, yaw, v, yaw_rate, accel_x, accel_y [N], wheel_speeds [N, 4]}.

The component is a vectorised batch (`sim_vehicle_ecu.batch.load_batch`, then
`require_vectorised`): a LoopBatch is refused here, for an executor that needs throughput.
"""
import math

import numpy as np
import torch

from . import npc


def _on_device(method):
    """A BatchRun method run in its device's context (`_OnDevice`)."""
    import functools

    @functools.wraps(method)
    def run(self, *a, **k):
        with self.on_device:
            return method(self, *a, **k)
    return run


class _OnDevice:
    """Every tensor a BatchRun method makes, on the run's device (092 K2.2c): torch's device
    context, so factories inside the run (zeros, full, tensor, arange) land there; nothing on a
    CPU run (torch 1.8 has no such context, and needs none)."""

    def __init__(self, device):
        self.device = device

    def __enter__(self):
        if self.device is not None:
            self.ctx = torch.device(self.device)
            self.ctx.__enter__()
        return self

    def __exit__(self, *exc):
        if self.device is not None:
            return self.ctx.__exit__(*exc)
        return False


SYNC_EVERY = 16     # a device run's steps per host check (BatchRun's sync_every)
CPU_SYNC_EVERY = 1  # a CPU run's: every step checked, the reference


def request_motion(kind, commands):
    """`(velocity [N], gear [N])` of the requests, as aib's Vehicle.apply takes them for the
    sticky-tire release: Autoware's velocity and gear; Ackermann's speed (0 when stale) and its
    sign's gear; a VESC's 0 and drive (what moves it is the component's alone)."""
    from sim_vehicle_ecu.signals import GEAR_DRIVE, GEAR_REVERSE
    n = len(next(iter(commands.values())))
    first = next(iter(commands.values()))
    if torch.is_tensor(first):          # a device-resident run: the same, in torch
        dev = first.device
        z = torch.zeros(n, dtype=torch.float64, device=dev)
        drive = torch.full((n,), GEAR_DRIVE, dtype=torch.int64, device=dev)
        if kind == "autoware":
            valid = commands.get("valid")
            valid = torch.ones(n, dtype=torch.bool, device=dev) if valid is None else valid
            return (torch.where(valid, commands["velocity"].to(torch.float64), z),
                    torch.where(valid, commands["gear"].to(torch.int64), drive))
        if kind == "ackermann":
            v = torch.where(torch.isinf(commands["age"]), z, commands["speed"].to(torch.float64))
            return v, torch.where(v < 0, torch.full_like(drive, GEAR_REVERSE), drive)
        return z, drive
    if kind == "autoware":
        valid = commands.get("valid", np.ones(n, bool))
        return (np.where(valid, commands["velocity"], 0.0),
                np.where(valid, commands["gear"], GEAR_DRIVE).astype(np.int64))
    if kind == "ackermann":
        v = np.where(np.isinf(commands["age"]), 0.0, commands["speed"])
        return v, np.where(v < 0, GEAR_REVERSE, GEAR_DRIVE).astype(np.int64)
    return np.zeros(n), np.full(n, GEAR_DRIVE, dtype=np.int64)


class BatchRun:
    def __init__(self, compiled, world, backend, component, route_length=300.0,
                 points=121, speed_limit=None, allow_loop=False, start_frames=0,
                 step_time=None, device=None, sync_every=None, anchors=None, model_dt=None):
        """`allow_loop`: accept a LoopBatch component (one Python step per slot), for checking
        a component before it has a batched form; never for a throughput number, and the run
        says so (`self.looped`). `anchors`: the map's resolved anchors ({name: anchor}, K9's
        anchors.resolved.json), which a car-follower's lane is taken from (092 K13).
        `model_dt` (s; default `step_time`): the step a behaviour model decides over at reset
        (issue 165), needed when the scenario has model entities."""
        self.anchors_resolved = dict(anchors or {})
        self.model_dt = model_dt if model_dt is not None else step_time
        from sim_vehicle_ecu import batch as ecu_batch
        # `device` (092 K2.2c): the run's tensors live there (the compiled scenario must be
        # compiled there too), and a component on array_api "torch" gets its commands and
        # sensors there; a numpy component gets them on the host (the CPU contract), each step
        self.device = None if device in (None, "cpu") else torch.device(device)
        self.on_device = _OnDevice(self.device)
        # a device run checks every `sync_every` steps (092 K2.2c): between, no host sync -- the
        # storyboard's and the vehicles' branches run as masked work, the actuation's check
        # and an element's overflow are kept as device flags, raised at the next check
        # (None: SYNC_EVERY on a device, CPU_SYNC_EVERY on the CPU; a value given runs lazy
        # on the CPU too, which is how the tests check the lazy ticks against the eager ones)
        if sync_every is None:
            sync_every = SYNC_EVERY if self.device is not None else CPU_SYNC_EVERY
        self.sync_every = max(1, int(sync_every))
        self._ticks = 0
        self._act_bad = None
        with self.on_device:
            self._init(compiled, world, backend, component, route_length, points, speed_limit,
                       allow_loop, start_frames, step_time, ecu_batch)

    def _init(self, compiled, world, backend, component, route_length, points, speed_limit,
              allow_loop, start_frames, step_time, ecu_batch):
        self.c, self.world, self.backend = compiled, world, backend
        self.looped = not getattr(component, "vectorised", False)
        self.component = component if allow_loop else ecu_batch.require_vectorised(component)
        self._ecu = ecu_batch
        if compiled.n != getattr(component, "n", compiled.n):
            raise ValueError(f"component has {component.n} slots, the batch {compiled.n}")
        egos = compiled.of_role("ego")
        if len(egos) != 1:
            raise ValueError(f"{compiled.scenario}: {len(egos)} egos, a batch has one policy")
        self.ego = egos[0]
        self.defaults = compiled.of_role("default")
        self.props = compiled.of_role("prop")
        self.route_length, self.points = route_length, points
        self.models = Models(self, compiled.of_role("model"))
        self.speed_limit = speed_limit
        self.vehicles = None
        self.first = None
        self.storyboard = compiled.storyboard
        from . import storyboard as sbmod
        self._sb = sbmod
        self.ctx = sbmod.Context(self)
        self.ctx.storyboard = self.storyboard
        nd = len(self.defaults)
        self.job = torch.zeros(compiled.n, nd, dtype=torch.int8)    # SSv2's LINEAR_ACCELERATION
        self.job_target = torch.zeros(compiled.n, nd, dtype=torch.float64)
        self.obs = None
        # the ego as SSv2's storyboard sees it (092 K2.4, API::updateFrame's order). Seats
        # tick k evaluates the storyboard at k * dt before anything else, on the ego the
        # previous tick read back; a tick reads the ego back before the world steps, so that
        # status is the world two frames before the one tick k's UpdateFrame makes (the
        # truth's ssv2 at frame f is its sim_pose at f - 1, read at f + 1's evaluation). This
        # step's world is that frame, so the storyboard reads the ego of two steps before
        # (`seen_before`); `seen` is the step before, kept to move into it. The NPCs it reads
        # are this step's (SSv2's canonical status, which the world shows this frame).
        # SSv2's default vehicles read that same ego (seen_before; see _observe).
        self.seen = None
        self.seen_before = None
        self.route = sbmod.RouteGoal(self)
        # SSv2's scenario time is A(S + k) - A(S): A the frames' step summed in a double from
        # the node's start, S the frames before startNpcLogic (SimulationClock; the fork's
        # clock_source:=simulator moves ROS time only). S differs from seats run to seats run;
        # a replay that must hit a SimulationTime boundary on the same frame passes its S.
        if start_frames and step_time is None:
            raise ValueError("start_frames needs the step_time it counts")
        a0 = 0.0
        for _ in range(int(start_frames)):
            a0 += step_time
        self.a0 = a0
        self.clock = torch.full((compiled.n,), a0, dtype=torch.float64)    # A
        self.clock0 = self.clock.clone()                                    # A(S)

    # --- reset ----------------------------------------------------------------------------

    @_on_device
    def reset(self, mask=None, preroll=None):
        """`preroll`: a callable the host runs once the ego and its component are reset and
        before the first observation and storyboard evaluation, to step the ego's physics
        through commands it ran before the scenario's time began (a seats ego's frames before
        startNpcLogic, 092 K2.4: its brake held by then). It drives the ego only, through
        before_physics and the host's physics step; nothing here moves SSv2's vehicles, ticks
        the storyboard or advances the clock meanwhile. It steps every slot's physics, so only
        a reset of every slot takes one."""
        c = self.c
        n = c.n
        mask = torch.ones(n, dtype=torch.bool) if mask is None else torch.as_tensor(mask)
        if self.device is not None:
            mask = mask.to(self.device)
        if preroll is not None and not bool(mask.all()):
            raise ValueError("an ego pre-roll steps every slot's physics: a reset of every "
                             "slot only")
        e = self.ego
        self.backend.reset(mask, c.x[:, e], c.y[:, e], c.yaw[:, e], c.speed[:, e])
        torch_component = getattr(self.component, "array_api_in_use", "numpy") == "torch"
        self.component.reset_batch(mask if torch_component else mask.cpu().numpy())
        self.first = mask.clone() if self.first is None else (self.first | mask)
        if preroll is not None:
            preroll(self)     # its first step clears `first`: the sensors have read by then
        if self.defaults:
            self._reset_vehicles(mask)
            self.job = torch.where(mask[:, None], torch.zeros_like(self.job), self.job)
        self.clock = torch.where(mask, torch.full_like(self.clock, self.a0), self.clock)
        self.clock0 = torch.where(mask, torch.full_like(self.clock0, self.a0), self.clock0)
        self.ctx.t = torch.where(mask, torch.zeros_like(self.ctx.t), self.ctx.t)
        self.ctx.standstill = torch.where(mask[:, None], torch.zeros_like(self.ctx.standstill),
                                          self.ctx.standstill)
        self.models.reset(mask)
        if self.storyboard is not None:
            self.storyboard.reset(mask)
        # No storyboard evaluation here: SSv2's first is a step after startNpcLogic (its tick
        # then has no time yet and starts the controllers), at scenario time dt, which the
        # first step's after_physics makes (092 K2.4: the batch evaluated at 0 too, a step
        # ahead of seats on every element's start)
        prev = self.obs
        st = self.backend.state()
        self.obs = self._observe(st, None)
        # the models decide on the reset observation, so their first command moves their
        # entities at step 1, as on seats (a model's first command answers the first frame of
        # NPC logic) and as SSv2's own NPCs first move (issue 165)
        self.models.decide_at_reset(st, self.obs, mask, self.model_dt)
        self.ctx.obs = self.obs
        self.route.reset(mask)
        if self.c.goal_waypoints:
            self.route.set(mask, self.c.goal_waypoints)
        self._tick(mask, evaluate=False)
        if prev is not None:      # the other slots keep this step's observation (and events)
            self.obs = _merge(prev, self.obs, mask)
            self.ctx.obs = self.obs
        # a reset slot's history is its reset pose, twice (seats: the ego held still before
        # startNpcLogic, by the pilot's hold or a pre-roll ending on it)
        seen = self._ego_view(self.obs)
        fresh = self.seen is None or prev is None
        self.seen = seen if fresh else _merge(self.seen, seen, mask)
        self.seen_before = seen if fresh else _merge(self.seen_before, seen, mask)
        return self.obs

    def _tick(self, mask=None, evaluate=True):
        sb = self.storyboard
        if sb is None:
            self.obs["route"] = self.route.update(self.obs)
            return
        if evaluate and mask is not None:
            keep = sb.outcome.clone()
            sb.outcome = torch.where(mask, sb.outcome, torch.full_like(sb.outcome, -1))
            sb.tick(self.ctx)
            sb.outcome = torch.where(mask, sb.outcome, keep)
        elif evaluate:
            sb.tick(self.ctx)
        self.obs["route"] = self.route.update(self.obs)
        self.obs["outcome"] = sb.outcome.clone()
        self.obs["storyboard_complete"] = sb.complete.clone()
        self.obs["storyboard_stopped"] = sb.stopped.clone()

    def outcome(self):
        """Each slot's outcome (storyboard.OUTCOMES): running, success or failure (an exit
        action). A slot whose storyboard completed or stopped is still running, as in SSv2
        (`storyboard.complete`, `storyboard.stopped`)."""
        sb = self.storyboard
        if sb is None:
            return ["running"] * self.c.n
        return [self._sb.OUTCOMES[int(k)] for k in sb.outcome]

    def limit_jobs(self, up, down, target):
        """A linear SpeedAction's acceleration (up) or deceleration (down) limit, held until
        the speed passes the target (SSv2's job, POST_UPDATE), then reset."""
        self.job = torch.where(up, torch.ones_like(self.job), torch.where(
            down, torch.full_like(self.job, 2), self.job))
        self.job_target = torch.where(up | down, target, self.job_target)

    def _post_update(self):
        veh = self.vehicles
        lazy = self._lazy()
        if veh is None or (not lazy and not bool((self.job != 0).any())):
            return
        done = (((self.job == 1) & (veh.v >= self.job_target))
                | ((self.job == 2) & (veh.v <= self.job_target)))
        if lazy or bool(done.any()):
            self._reset_constraints(done)
            self.job = torch.where(done, torch.zeros_like(self.job), self.job)

    def _reset_constraints(self, m):
        veh = self.vehicles
        for k, val in npc.DEFAULT_CONSTRAINTS.items():
            setattr(veh.c, k, torch.where(m, torch.full_like(getattr(veh.c, k), val),
                                          getattr(veh.c, k)))

    def _reset_vehicles(self, mask):
        c, d = self.c, self.defaults
        x, y, yaw = c.x[:, d], c.y[:, d], c.yaw[:, d]
        pts = self.world.route(x, y, yaw, self.route_length, self.points)   # [N, D, P, 2]
        # world.route samples SSv2's spline at equal arc length: a smooth route on that length
        routes = npc.Routes(pts.to(torch.float64),
                            spacing=self.route_length / max(self.points - 1, 1))
        length = torch.tensor([c.entities[i].length for i in d],
                              dtype=torch.float64).expand(c.n, len(d)).clone()
        width = torch.tensor([c.entities[i].width for i in d],
                             dtype=torch.float64).expand(c.n, len(d)).clone()
        limit = (self.speed_limit if self.speed_limit is not None
                 else self.world.speed_limit(x, y)) * torch.ones_like(x)
        cx = torch.tensor([c.entities[i].cx for i in d],
                          dtype=torch.float64).expand(c.n, len(d)).clone()
        fresh = npc.DefaultVehicles(routes, torch.zeros_like(x), c.speed[:, d].clone(), length,
                                    width, limit, cx=cx)
        # an Init SpeedAction is the target too (a step to it, held); without one SSv2 drives
        # at the route's speed limit
        fresh.set_target_speed(c.speed[:, d], c.speed_set[:, d])
        fresh.world, fresh.route_length = self.world, self.route_length
        if self.vehicles is None:
            self.vehicles = fresh
            return
        m = mask[:, None].expand_as(x)
        old = self.vehicles
        for name in ("s", "v", "a", "jerk", "target", "length", "width", "speed_limit", "mode"):
            setattr(old, name, torch.where(m, getattr(fresh, name), getattr(old, name)))
        self._reset_constraints(m)
        old.routes.points = torch.where(m[..., None, None], fresh.routes.points, old.routes.points)
        old.routes = npc.Routes(old.routes.points, spacing=old.routes.spacing)
        old.lc = old.lc & ~m         # a reset slot's lane changes end with it
        for k in torch.nonzero(mask).flatten().tolist():
            old.lc_to_lane[k] = [None] * len(old.lc_to_lane[k])

    # --- step -----------------------------------------------------------------------------

    def _sensors(self, st):
        # a torch component takes the backend's tensors where they are (092 K2.2c); a numpy
        # one, host arrays: the CPU contract, a copy each step
        torch_component = getattr(self.component, "array_api_in_use", "numpy") == "torch"
        conv = (lambda t: t) if torch_component else (lambda t: t.detach().cpu().numpy())  # noqa
        valid = ~self.first if torch_component else ~self.first.cpu().numpy()
        out = {"wheel_speeds": conv(st["wheel_speeds"]), "yaw_rate": conv(st["yaw_rate"]),
               "accel_x": conv(st["accel_x"]), "accel_y": conv(st["accel_y"]),
               "valid": valid}
        truth = tuple(getattr(self.component, "truth", ()))
        if truth:
            avail = {"speed": st["v"], "yaw": st["yaw"], "yaw_rate": st["yaw_rate"],
                     "pose": torch.stack([st["x"], st["y"], st["yaw"]], -1)}
            missing = [t for t in truth if t not in avail]
            if missing:
                raise ValueError(f"the component declares truth {missing}, which the batch "
                                 "does not provide yet")
            out["truth"] = {t: conv(avail[t]) for t in truth}
            out["truth_valid"] = {t: (valid.clone() if torch_component else valid.copy())
                                  for t in truth}
        return out

    @_on_device
    def step(self, commands, dt):
        """One step of every slot, the engine stepped here: before_physics, the backend's
        advance, after_physics. Returns after_physics' observation."""
        self.before_physics(commands, dt)
        self.backend.advance(dt)
        return self.after_physics(dt)

    @_on_device
    def before_physics(self, commands, dt):
        """The ego's component on what its sensors read, its actuation handed to the backend:
        what a host that owns the physics loop (Isaac Lab's DirectRLEnv) calls before each
        physics step, then steps the engine itself, then calls after_physics.

        A command dict passed again (the same object, as an env holds one action over its
        decimation's substeps) is one message held: its `age` grows by each step's dt, so a
        component that times a held command out (roboracer_vesc's 0.5 s) sees it age, and a
        new dict, at its own age, is a new message. Without this the held one stayed at age 0,
        read as the message the component already had, and timed out (094 P2: the MuSHR
        stalled at 0.33 m/s)."""
        self._set_lazy()
        st = self.backend.state()
        commands = self._held(commands, dt)
        self._held_dt = dt
        act = self.component.step_batch(commands, self._sensors(st), dt)
        if self._lazy() and isinstance(act, dict) and torch.is_tensor(act.get("drive")):
            self._check_deferred(act)
        else:
            act = self._ecu.checked_batch(act, self.c.n, "ego component")
        self.first = torch.zeros_like(self.first)
        velocity, gear = request_motion(self.component.commands, commands)
        if self.device is not None and not torch.is_tensor(act["drive"]):
            # a numpy component on a device run: its actuation back to the device
            act = {k: (torch.as_tensor(v, device=self.device) if k != "telemetry" else v)
                   for k, v in act.items()}
        self.backend.apply(act, velocity=velocity, gear=gear)
        return act

    def _held(self, commands, dt):
        """`commands` with its age grown by the time it has been held (before_physics)."""
        if not isinstance(commands, dict) or "age" not in commands:
            return commands
        if commands is not getattr(self, "_held_cmd", None):
            self._held_cmd, self._held_t = commands, 0.0
            return commands
        self._held_t += self._held_dt
        out = dict(commands)
        out["age"] = commands["age"] + self._held_t
        return out

    @_on_device
    def after_physics(self, dt):
        """After one physics step: the ego read back, SSv2's default vehicles moved, the
        storyboard evaluated at the new time. Returns the observation: the ego's state, every
        entity's pose [N, E] (x, y, yaw, v) and each slot's outcome."""
        self._set_lazy()
        before = self.seen_before
        self.seen_before = self.seen
        st = self.backend.state()
        self.models.step(st, dt)     # behaviour models, on this step's ego (092 K10)
        self.obs = self._observe(st, dt, npc_ego=before)
        # car-followers read their leaders where this step left every entity (092 K13)
        self.models.step_followers(self.obs, dt)
        self.seen = self._ego_view(self.obs)
        view = self._as_ssv2_sees(self.obs, before)
        self._post_update()
        live = (self.storyboard.outcome == 0 if self.storyboard is not None
                else torch.ones(self.c.n, dtype=torch.bool))
        self.clock = torch.where(live, self.clock + dt, self.clock)
        self.ctx.t = self.clock - self.clock0
        self.ctx.update(view, dt)
        self._tick()
        if not self._lazy():
            self._check()
        self._ticks += 1
        return self.obs

    def _lazy(self):
        """Whether this step skips its host checks (a device run between its checks)."""
        return self.sync_every > 1 and self._ticks % self.sync_every != 0

    def _set_lazy(self):
        lazy = self._lazy()
        if self.storyboard is not None:
            self.storyboard.lazy = lazy
        if self.vehicles is not None:
            self.vehicles.lazy = lazy

    def _check_deferred(self, act):
        """The actuation check without a sync: the shapes on the host, the values into a
        device flag (`_check` raises it)."""
        n = self.c.n
        for f, shape in (("drive", (n, 4)), ("brake", (n, 4)), ("tire_angle", (n,))):
            a = act.get(f)
            if not torch.is_tensor(a) or tuple(a.shape) != shape:
                self._ecu.checked_batch(act, n, "ego component")    # raises, naming it
        bad = ~(torch.isfinite(act["drive"]).all() & torch.isfinite(act["brake"]).all()
                & torch.isfinite(act["tire_angle"]).all() & (act["brake"] >= 0).all())
        self._act_bad = bad if self._act_bad is None else (self._act_bad | bad)

    def _check(self):
        """What the lazy steps since the last check kept on the device, raised."""
        if self._act_bad is not None:
            bad, self._act_bad = self._act_bad, None
            if bool(bad):
                raise self._ecu.BatchError(
                    "ego component: actuation not finite, or a brake negative, in a step since "
                    f"step {self._ticks - self.sync_every + 1} (rerun from the same seed with sync_every=1 "
                    "to name the slot)")
        if self.storyboard is not None:
            self.storyboard.check()
        veh = self.vehicles
        if veh is not None and veh.lc_started and not bool(veh.lc.any()):
            veh.lc_started = False     # no lane change left: its steps skipped again

    def _ego_view(self, obs):
        """The ego's columns of an observation (x, y, yaw, v [N]) and its state dict, and the
        model entities' columns ([N, M]): what SSv2 holds of the world-owned entities."""
        e = self.ego
        view = {"x": obs["x"][:, e].clone(), "y": obs["y"][:, e].clone(),
                "yaw": obs["yaw"][:, e].clone(), "v": obs["v"][:, e].clone(),
                "ego": {k: v.clone() for k, v in obs["ego"].items()}}
        if self.models.idx:
            view["models"] = {k: obs[k][:, self.models.idx].clone()
                              for k in ("x", "y", "yaw", "v")}
        return view

    def _as_ssv2_sees(self, obs, seen):
        """`obs` with the ego's columns and state from `seen` (two steps before), and the model
        entities' columns: on seats they are world-owned as the ego is, so SSv2 has their pose
        when it has the ego's (092 K10's agreement, run 1: the far kerb two steps early)."""
        if seen is None:
            return obs
        e = self.ego
        view = dict(obs)
        for k in ("x", "y", "yaw", "v"):
            col = obs[k].clone()
            col[:, e] = seen[k]
            if "models" in seen:
                col[:, self.models.idx] = seen["models"][k]
            view[k] = col
        view["ego"] = seen["ego"]
        return view

    def _observe(self, st, dt, npc_ego=None):
        """Every entity's pose; with `dt`, SSv2's default vehicles moved by it first.
        `npc_ego` (an _ego_view): the ego as those vehicles see it, else as it is now. SSv2's
        update in tick k reads the ego that tick read back, w(k-1), and the poses it makes
        reach the world at frame k+1 (sent with tick k+1's status): the vehicle at frame f
        reacted to the ego at f-2, so after_physics hands them the ego of two steps before
        (092 K2.4: k24_npc_stops_for_ego's follower 0.072 m max off, against 0.199 m on the
        current ego and 0.159 m on the step before). The observation's ego stays current."""
        c = self.c
        x, y, yaw = c.x.clone(), c.y.clone(), c.yaw.clone()
        v = torch.zeros_like(x)
        x[:, self.ego], y[:, self.ego], yaw[:, self.ego], v[:, self.ego] = (
            st["x"], st["y"], st["yaw"], st["v"])
        if self.defaults:
            if getattr(self, "_others", None) is None:   # once: the indices and boxes on the device
                idx = [self.ego] + self.props
                f64 = lambda q: torch.tensor(q, dtype=torch.float64)   # noqa: E731
                self._others = (torch.tensor(idx, dtype=torch.int64),
                                f64([c.entities[i].length for i in idx]),
                                f64([c.entities[i].width for i in idx]),
                                f64([c.entities[i].cx for i in idx]),
                                torch.tensor(self.defaults, dtype=torch.int64))
            others_idx, ego_len, ego_wid, ego_cx, _ = self._others
            others = {"x": x[:, others_idx].clone(), "y": y[:, others_idx].clone(),
                      "yaw": yaw[:, others_idx].clone(), "v": v[:, others_idx].clone(),
                      "length": ego_len.expand(c.n, -1), "width": ego_wid.expand(c.n, -1),
                      "cx": ego_cx.expand(c.n, -1)}
            if npc_ego is not None:         # column 0 is the ego
                for k in ("x", "y", "yaw", "v"):
                    others[k][:, 0] = npc_ego[k]
            nx, ny, nyaw = (self.vehicles.step(dt, others) if dt is not None
                            else self.vehicles.poses())
            d = self._others[4]
            x[:, d], y[:, d], yaw[:, d], v[:, d] = nx, ny, nyaw, self.vehicles.v
        out = {"x": x, "y": y, "yaw": yaw, "v": v, "ego": st}
        self.models.place(out)
        return out



class Models:
    """The batch's behaviour-model entities (092 K10): one model per entity, its slots on the
    run's device (array_api "torch"). Each step after the ego's physics, a model reads that
    step's ego truth and its own pose, and its command (speed, heading, an acceleration
    limit) moves its entity kinematically: speed toward the command within the limit, then
    along the heading. Seats run the same model on numpy as a K4 attachment, through K12's
    entity_command, so the two forms differ only in how the world integrates the command and
    in the seats' latency (the agreement check measures both).

    The crossing's anchors come from the model's `anchor.*` properties and its Init pose:
    `kerb` is `anchor.approach` metres ahead along its heading (default the model's
    `approach`, else 0); `far` is `anchor.crossing` metres further (default 7 m); `conflict`
    is where that line meets the ego's route (its first crossing), or the line's middle if the
    route does not meet it."""

    def __init__(self, run, indices):
        self.run, self.idx = run, list(indices)
        self.models, self.events = [], {}
        self.follower = []
        if not self.idx:
            return
        from scensim import behaviour
        from sim_vehicle_ecu import xp as xpmod
        c = run.c
        self.xp = xpmod.namespace("torch", None if run.device is None else str(run.device))
        self.cls = behaviour.MODELS
        n = c.n
        z = torch.zeros(n, len(self.idx), dtype=torch.float64)
        self.x, self.y, self.yaw, self.v = z.clone(), z.clone(), z.clone(), z.clone()
        self._prev_v = None
        self.pending = [None] * len(self.idx)   # each model's command, applied the next step
        # a car-follower (092 K13) steps on every entity's pose after the step, not the ego's
        self.follower = [c.entities[i].model["model"] == "idm_follower" for i in self.idx]
        self.anchors = [self._anchors(j, i) for j, i in enumerate(self.idx)]

    def _anchors(self, j, i):
        """Per slot, entity i's crossing in the map frame; a car-follower's lane."""
        run = self.run
        if self.follower[j]:
            from scensim.behaviour.follower import lane_anchors
            return lane_anchors(run.c.entities[i].model["params"], run.anchors_resolved)
        return model_anchors(run.c, run.world, i, run.ego, run.route_length, run.points)

    def reset(self, mask):
        if not self.idx:
            return
        c = self.run.c
        if not self.models:       # built at the first reset, every slot
            for j, i in enumerate(self.idx):
                spec = c.entities[i].model
                cls = self.cls[spec["model"]]
                self.models.append(cls(spec["params"], spec["seeds"], self.anchors[j], self.xp))
        else:
            for m in self.models:
                m.reset(mask)
        cols = torch.tensor(self.idx, dtype=torch.int64, device=c.x.device)
        m2 = mask[:, None].expand_as(self.x)
        self.x = torch.where(m2, c.x[:, cols], self.x)
        self.y = torch.where(m2, c.y[:, cols], self.y)
        self.yaw = torch.where(m2, c.yaw[:, cols], self.yaw)
        self.v = torch.where(m2, torch.zeros_like(self.v), self.v)
        self._prev_v = None
        for j, p in enumerate(self.pending):     # a reset slot has no command yet
            if p is not None:
                p["accel_limit"] = torch.where(mask, torch.zeros_like(p["accel_limit"]),
                                               p["accel_limit"])
                p["speed"] = torch.where(mask, torch.zeros_like(p["speed"]), p["speed"])
                p["heading"] = torch.where(mask, self.yaw[:, j], p["heading"])

    def step(self, st, dt):
        if not self.idx:
            return
        n = self.run.c.n
        if "vx_map" in st:   # the map-frame velocity, what the walker sees (092 K10's agreement)
            vx, vy = st["vx_map"], st["vy_map"]
        else:                # v along the body: a sliding ego's lateral velocity is dropped
            vx = st["v"] * torch.cos(st["yaw"])
            vy = st["v"] * torch.sin(st["yaw"])
        if self._prev_v is None:
            ax, ay = torch.zeros_like(vx), torch.zeros_like(vy)
        else:
            ax, ay = (vx - self._prev_v[0]) / dt, (vy - self._prev_v[1]) / dt
        self._prev_v = (vx, vy)
        valid = torch.ones(n, dtype=torch.bool, device=vx.device)
        for j in range(len(self.models)):
            self._move(j, dt)
        self._decide(st["x"], st["y"], vx, vy, ax, ay, valid, dt)

    def _decide(self, ex, ey, vx, vy, ax, ay, valid, dt, mask=None):
        """The ego-reading models' decisions on the ego's state; a command where `mask` (every
        slot: None) becomes pending, the others keep theirs."""
        for j, m in enumerate(self.models):
            if self.follower[j]:
                continue
            obs = {"x": self.x[:, j], "y": self.y[:, j], "ego_x": ex, "ego_y": ey,
                   "ego_vx": vx, "ego_vy": vy, "ego_ax": ax, "ego_ay": ay, "valid": valid}
            act, ev = m.step(obs, dt)
            self._pend(j, act, mask)
            self.events[self.run.c.entities[self.idx[j]].name] = ev

    def _pend(self, j, act, mask):
        new = {k: act[k] for k in ("speed", "heading", "accel_limit")}
        old = self.pending[j]
        if mask is not None and old is not None:
            new = {k: torch.where(mask, new[k], old[k]) for k in new}
        self.pending[j] = new

    def decide_at_reset(self, st, obs, mask, dt):
        """Issue 165: every model decides once on the reset observation (`obs`, the ego's
        state `st`), for the reset slots (`mask`) only, so its first command is pending for
        step 1 and moves its entity there; nothing moves now. On seats a model's first command
        answers the first frame of NPC logic (issue 163) and moves the entity a frame later, as
        SSv2's own NPCs first move."""
        if not self.idx:
            return
        if dt is None:
            raise ValueError("a scenario with behaviour models needs BatchRun's model_dt (or "
                             "step_time): the step its models decide over at reset")
        if "vx_map" in st:
            vx, vy = st["vx_map"], st["vy_map"]
        else:
            vx = st["v"] * torch.cos(st["yaw"])
            vy = st["v"] * torch.sin(st["yaw"])
        z = torch.zeros_like(vx)
        self._prev_v = (vx, vy) if self._prev_v is None else (
            torch.where(mask, vx, self._prev_v[0]), torch.where(mask, vy, self._prev_v[1]))
        self._decide(st["x"], st["y"], vx, vy, z, z, mask, dt, mask)
        self.step_followers(obs, dt, valid=mask, mask=mask)
        obs["model_events"] = dict(self.events)

    def _move(self, j, dt):
        """The previous step's command moves model j's entity first: the lockstep channel's lag
        1 (092 K12), so a model on seats and in the batch reacts a frame after it decides."""
        p = self.pending[j]
        if p is not None:
            self.x[:, j], self.y[:, j], self.v[:, j] = model_law(
                self.x[:, j], self.y[:, j], self.v[:, j],
                p["speed"], p["heading"], p["accel_limit"], dt)
            self.yaw[:, j] = p["heading"]

    def step_followers(self, obs, dt, valid=None, mask=None):
        """The car-followers (092 K13), each on its own pose and its leader's in `obs` (every
        entity where this step left it, the models placed), as on seats a follower reads one
        truth frame; their poses and events placed back into `obs`."""
        if not any(self.follower):
            return
        n = self.run.c.n
        names = [e.name for e in self.run.c.entities]
        if valid is None:
            valid = torch.ones(n, dtype=torch.bool, device=obs["x"].device)
        for j, m in enumerate(self.models):
            if not self.follower[j]:
                continue
            leader = m.params[0]["leader"]
            li = names.index(leader) if leader in names else None
            vx, vy = self.v[:, j] * torch.cos(self.yaw[:, j]), self.v[:, j] * torch.sin(self.yaw[:, j])
            if li is None:
                lx, ly, lvx, lvy = self.x[:, j], self.y[:, j], vx, vy
                lvalid = torch.zeros(n, dtype=torch.bool, device=valid.device)
            else:
                lv, lyaw = obs["v"][:, li], obs["yaw"][:, li]
                lx, ly = obs["x"][:, li], obs["y"][:, li]
                lvx, lvy = lv * torch.cos(lyaw), lv * torch.sin(lyaw)
                lvalid = valid
            act, ev = m.step({"x": self.x[:, j], "y": self.y[:, j], "vx": vx, "vy": vy,
                              "leader_x": lx, "leader_y": ly, "leader_vx": lvx,
                              "leader_vy": lvy, "leader_valid": lvalid, "valid": valid}, dt)
            self._pend(j, act, mask)
            self.events[self.run.c.entities[self.idx[j]].name] = ev
        obs["model_events"] = dict(self.events)

    def place(self, obs):
        """The model entities' poses into an observation's [N, E] columns, and their events."""
        if not self.idx:
            return
        for j, i in enumerate(self.idx):
            obs["x"][:, i], obs["y"][:, i] = self.x[:, j], self.y[:, j]
            obs["yaw"][:, i], obs["v"][:, i] = self.yaw[:, j], self.v[:, j]
        obs["model_events"] = dict(self.events)

    def records(self):
        """Per model entity, each slot's record (the model's own `record()`)."""
        return {self.run.c.entities[i].name: m.record() for i, m in zip(self.idx, self.models)}


def model_anchors(c, world, i, ego, route_length=300.0, points=121):
    """Per slot of compiled scenario `c`, model entity i's crossing in the map frame: `kerb`
    `anchor.approach` m ahead of its Init pose along its heading (default the model's
    `approach`, else 0), `far` `anchor.crossing` m further (default 7), `conflict` where that
    line first meets the ego's route on `world` (else its middle). The batch's models (Models)
    and the seats runner (scensim.behaviour.seats) both take their anchors from here."""
    e = c.entities[i]
    route = world.route(c.x[:, ego:ego + 1].cpu(), c.y[:, ego:ego + 1].cpu(),
                        c.yaw[:, ego:ego + 1].cpu(), route_length, points)
    out = []
    for k in range(c.n):
        p, a = e.model["params"][k], e.model["anchors"][k]
        x0, y0, h = float(c.x[k, i]), float(c.y[k, i]), float(c.yaw[k, i])
        dx, dy = math.cos(h), math.sin(h)
        ap = a.get("approach", p.get("approach") or 0.0)
        cross = a.get("crossing", 7.0)
        kx, ky = x0 + ap * dx, y0 + ap * dy
        fx, fy = kx + cross * dx, ky + cross * dy
        cp = _first_crossing(route[k, 0].tolist(), (kx, ky), (fx, fy))
        out.append({"kerb": [kx, ky], "far": [fx, fy],
                    "conflict": list(cp) if cp else [(kx + fx) / 2, (ky + fy) / 2]})
    return out


def model_law(x, y, v, speed, heading, accel_limit, dt):
    """A behaviour model's command moves its entity (092 K10, K12 D5): the speed toward the
    commanded speed by at most `accel_limit` dt, then `v dt` along the heading (the yaw is the
    heading). The new (x, y, v), torch tensors. The CARLA world server integrates a COMMANDED
    body by the same law (scensim_carla_world's commanded.rs), checked against this one on a
    shared fixture (tests/fixtures/k12_models_law.json there; test_model_law here)."""
    lim = accel_limit * dt
    v = v + torch.maximum(torch.minimum(speed - v, lim), -lim)
    return x + v * torch.cos(heading) * dt, y + v * torch.sin(heading) * dt, v


def _first_crossing(points, a, b):
    """Where the polyline `points` first crosses the segment a-b, or None."""
    (ax, ay), (bx, by) = a, b
    for (px, py), (qx, qy) in zip(points, points[1:]):
        d = (bx - ax) * (qy - py) - (by - ay) * (qx - px)
        if abs(d) < 1e-12:
            continue
        t = ((px - ax) * (qy - py) - (py - ay) * (qx - px)) / d
        u = ((px - ax) * (by - ay) - (py - ay) * (bx - ax)) / d
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return ax + t * (bx - ax), ay + t * (by - ay)
    return None


def _merge(old, new, mask):
    """`new` for the slots in `mask`, `old` for the others: tensors whose first dimension is
    the slots, recursively through dicts; anything else is `new`'s."""
    if isinstance(new, dict):
        return {k: (_merge(old[k], v, mask) if isinstance(old, dict) and k in old else v)
                for k, v in new.items()}
    if (torch.is_tensor(new) and torch.is_tensor(old) and new.shape == old.shape
            and new.dim() >= 1 and new.shape[0] == mask.shape[0]):
        m = mask.reshape(-1, *([1] * (new.dim() - 1)))
        return torch.where(m, new, old)
    return new


_ = np
