"""Backend A of the batch (roadmap 092 K2.2, batch-executor.md section 5): N copies of the
same PhysX vehicle seats run (aib's `Vehicle`, built from the car's rig), one per slot, each in
its own place on the stage. It is the same car as seats, physics and tire model alike, so a
batch run on it can be checked against a seats run (K2.4). It is not vectorised: Isaac Sim's
physics tensor API has no vehicle view, so each car's actuation (four drive and brake
torques, the steer angles) is written and its wheel states read one car at a time. It says so
(`vectorised = False`), and a throughput bench refuses it as it refuses a LoopBatch; backend B
(an articulation car) is the fast one.

The backend's contract is core.BatchRun's: reset(mask, x, y, yaw, speed), apply(actuation),
advance(dt), state(). Import after Isaac Sim's `SimulationApp`.

Slots stand apart on a grid (`spacing`, m), so cars of different slots never touch. A slot's
poses are the scenario's, offset by its origin; state() takes the origin off again.
"""
import math

import numpy as np
import torch

# How far a car may be from where its reset put it, at its first sample after (m; along its
# heading, plus a substep's travel). The errors this is for are an env's origin (issue 109,
# metres) or the travel since a lost reset (issue 110, tens of metres). Misses of 1.2 and 1.4 cm
# across (094 P4's engine A smokes) and 5.2 cm across (seed 1 at 1024 envs, iteration 187) are
# unexplained, under investigation in issue 113: one substep (1/120 s) after a reset they are
# 1.4 to 6 m/s sideways, not a car settling (243). Do not widen it before 113 finds the cause.
LANDING_TOLERANCE = 0.05
# How far a car's PhysX velocity may be from its reset's, at the same sample (m/s, along and
# across the reset's heading): a reset that kept the car's old motion, or lost its Init speed
# (issue 113), at any speed, which the pose check sees only as u * dt.
LANDING_VELOCITY_TOLERANCE = 0.5
# and its yaw rate's from 0 (rad/s): a reset that kept the car's old turn (issue 113)
LANDING_YAW_RATE_TOLERANCE = 0.2
# Two cars' bodies overlap when their centres are this close (m; a Model 3 is 4.7 m by 1.9 m)
CLOSE_M = 2.0
# engine A's runs warn when two cars come closer than this (m; issue 113's layout keeps every
# pair a route gap plus the boxes' margins apart)
SEPARATION_WARN = 5.0


class PhysxVehicleBackend:
    vectorised = False   # one car at a time through PhysX's vehicle interface (no vehicle view)

    def __init__(self, world, stage, physx, rig, n, spacing=200.0, root="/World/envs",
                 z=0.0, velocity_set=True, origins=None):
        """`world`: what `advance` steps (None for a host that owns the physics loop and calls
        actuate, its own step, then sample); `origins` [N, 2]: each slot's place (Isaac Lab's
        env origins), else a grid at `spacing`."""
        from aib.isaac.vehicle import Vehicle, ensure_vehicle_scene
        from aib.control import State

        self.world, self.stage, self.physx, self.rig, self.n = world, stage, physx, rig, n
        self.z, self.velocity_set = z, velocity_set
        side = max(1, math.ceil(math.sqrt(n)))
        self.origins = (np.asarray(origins, dtype=np.float64)[:, :2] if origins is not None else
                        np.array([((i % side) * spacing, (i // side) * spacing)
                                  for i in range(n)], dtype=np.float64))
        ensure_vehicle_scene(stage)
        # aib writes a car's pose as its prim's own transform, relative to its parent: each env
        # prim's place in the world, subtracted from the world poses handed to it. Isaac Lab 3.0
        # puts env_0's prim at its origin and leaves the others at the world's (their origins
        # live in Fabric), so a world pose put env_0's car at twice its origin (P4: its local y
        # read as the origin's, off the road at once, reset every step)
        self.parent = np.zeros((n, 3))
        from pxr import UsdGeom
        cache = UsdGeom.XformCache()
        for i in range(n):
            env = stage.GetPrimAtPath(f"{root}/env_{i}")
            if env.IsValid():
                m = cache.GetLocalToWorldTransform(env)
                if any(abs(m[r_][c_] - (1.0 if r_ == c_ else 0.0)) > 1e-9
                       for r_ in range(3) for c_ in range(3)):
                    raise RuntimeError(f"{root}/env_{i} is rotated or scaled: a car's pose, "
                                       "written relative to it, would be too (issue 109)")
                t = m.ExtractTranslation()
                self.parent[i] = (t[0], t[1], t[2])
        self._landing = {}   # slot -> its reset's world (x, y, speed, yaw, before): checked at its sample
        self.landing_log = None   # a file: one JSON line per reset, at its first sample (issue 113)
        self.landing_raise = True  # False: log a miss and carry on (issue 113's reproduction only)
        # the smallest distance between two cars (of different envs: one each), every
        # `separation_every` samples (the env's decimation: once a policy step), its minimum over
        # `separation_window` of those printed and warned of under SEPARATION_WARN (133, issue 113)
        self.separation_every, self.separation_window = 1, 24
        self._sep = {"samples": 0, "checks": 0, "min": math.inf, "pair": None, "window": 0}
        self.landing_max = {"pose_across": 0.0, "pose_along": 0.0, "v_across": 0.0, "v_along": 0.0,
                            "resets": 0}
        self.cars, self.states = [], []
        for i in range(n):
            ox, oy = self.origins[i]
            path = f"{root}/env_{i}/ego"
            self.cars.append(Vehicle(stage, path, rig.vehicle, rig.make_component(),
                                     rig.box_center, rig.box_dims,
                                     (self._local(i, (ox, oy, z)), (1, 0, 0, 0)),
                                     ground_clearance=rig.ground_clearance))
            self.states.append(State())
        self.act = None
        self.timing = {"actuate": 0.0, "physics": 0.0, "sample": 0.0, "steps": 0}
        self.trace_steps = 0   # > 0: record slot 0's PhysX read-back for that many steps
        self.trace = []

    # --- the contract ------------------------------------------------------------------------

    def reset(self, mask, x, y, yaw, speed):
        from pxr import Gf, UsdPhysics

        for i in np.flatnonzero(np.asarray(mask, bool)):
            ox, oy = self.origins[i]
            h = float(yaw[i])
            pose = ((ox + float(x[i]), oy + float(y[i]), self.z),
                    (math.cos(h / 2), 0.0, 0.0, math.sin(h / 2)))
            car = self.cars[i]
            # before: the car as its last sample read it (world position, PhysX velocity)
            before = (None if car.last is None else
                      (tuple(car.last[0][:2]), tuple(car.last[2][:2]),
                       float(self.states[i].angular_velocity[2])))
            car.teleport((self._local(i, pose[0]), pose[1]), self.physx)
            self._landing[int(i)] = (pose[0][0], pose[0][1], float(speed[i]), h, before)
            v = float(speed[i])
            if v and self.velocity_set:
                # the Init speed: the body along its heading, the wheels rolling with it
                body = UsdPhysics.RigidBodyAPI(self.stage.GetPrimAtPath(car.path))
                body.GetVelocityAttr().Set(Gf.Vec3f(v * math.cos(h), v * math.sin(h), 0.0))
                spin = v / self.rig.vehicle.wheel_radius
                for wp in car.wheel_paths:
                    try:
                        self.physx.set_wheel_rotation_speed(wp, spin)
                    except Exception:   # noqa: BLE001 - not simulated yet
                        pass
            # the reset's observation reads the spawn, not State's origin (K2.4: step 0's ego
            # was at (0, 0) until the first physics step's read-back)
            self.states[i].__init__(position=pose[0], quat=pose[1],
                                    velocity=(v if self.velocity_set else 0.0, 0.0, 0.0))

    def _check_landing(self, dt):
        """Each slot reset since the last sample is where its reset put it, by PhysX's own world
        pose and velocity, in its reset's heading frame: within LANDING_TOLERANCE across and of
        its reset's travel along (its speed for a substep), and its velocity within
        LANDING_VELOCITY_TOLERANCE of its reset's speed along and of 0 across. A car elsewhere is
        an env prim whose transform reached USD after this backend read it (issue 109: off by its
        env's origin, metres) or a teleport PhysX never saw (issue 110: off by its travel since,
        tens of metres); a car moving otherwise is a reset that kept or lost a velocity (issue
        113). Raised. Every reset is logged to `landing_log` (one JSON line: the reset, the car
        before it, the miss), and the largest misses kept in `landing_max`."""
        import json
        bad = []
        m = self.landing_max
        # every car's world (x, y) at this sample: the nearest other car to each reset one (243:
        # another env's car on the reset spot, if the envs' collision filter misses aib's cars)
        xy = np.array([st.position[:2] for st in self.states], dtype=np.float64)
        for i, (x, y, v, h, before) in self._landing.items():
            px, py = (float(c) for c in self.states[i].position[:2])
            c, s_ = math.cos(h), math.sin(h)
            frame = lambda wx, wy: (wx * c + wy * s_, -wx * s_ + wy * c)  # noqa: E731
            along, across = frame(px - x, py - y)
            last = self.cars[i].last
            vw = (float(last[2][0]), float(last[2][1])) if last is not None else (0.0, 0.0)
            v_along, v_across = frame(*vw)
            yaw_rate = float(self.states[i].angular_velocity[2])
            m["resets"] += 1
            m["pose_across"] = max(m["pose_across"], abs(across))
            m["pose_along"] = max(m["pose_along"], abs(along - v * dt))
            m["v_across"] = max(m["v_across"], abs(v_across))
            m["v_along"] = max(m["v_along"], abs(v_along - v))
            m["yaw_rate"] = max(m.get("yaw_rate", 0.0), abs(yaw_rate))
            fail = (abs(across) > LANDING_TOLERANCE or
                    abs(along - v * dt) > LANDING_TOLERANCE + abs(v) * dt or
                    abs(v_across) > LANDING_VELOCITY_TOLERANCE or
                    abs(v_along - v) > LANDING_VELOCITY_TOLERANCE or
                    abs(yaw_rate) > LANDING_YAW_RATE_TOLERANCE)
            if self.landing_log is not None or fail:
                line = {"slot": int(i), "v": round(v, 4), "yaw": round(h, 5),
                        "along": round(along, 4), "across": round(across, 4),
                        "v_along": round(v_along, 4), "v_across": round(v_across, 4),
                        "yaw_rate": round(yaw_rate, 4), "usd": self._usd_velocity(i),
                        # the first substep's steer and the body's height, its vertical speed
                        "tire_angle": round(float(self.cars[i].tire_angle), 4),
                        "z": round(float(self.states[i].position[2]), 4),
                        "v_z": round(float(last[2][2]) if last is not None else 0.0, 4)}
                d = np.hypot(xy[:, 0] - px, xy[:, 1] - py)
                d[i] = np.inf
                k = int(np.argmin(d))
                line["nearest"] = [k, round(float(d[k]), 3)]
                if before is not None:
                    bp, bv, bw = before
                    line["before_yaw_rate"] = round(bw, 4)
                    line["before_v_along"], line["before_v_across"] = (round(a, 4)
                                                                       for a in frame(*bv))
                    line["before_from_reset"] = [round(a, 3) for a in frame(bp[0] - x, bp[1] - y)]
                if fail:
                    line["fail"] = True
                    bad.append(line)
                if self.landing_log is not None:
                    self.landing_log.write(json.dumps(line) + "\n")
        self._landing = {}
        if self.landing_log is not None:
            self.landing_log.flush()
        if bad and self.landing_raise:
            raise RuntimeError("cars not where or not moving as their resets put them (reset "
                               f"frame; m, m/s): {bad} (issues 109, 110, 113)")

    def _separation(self):
        """The cars' smallest distance apart, once every `separation_every` samples; each
        `separation_window` checks its minimum printed (and logged), with a warning under
        SEPARATION_WARN (issue 113: engine A's layout keeps them apart, or the run is wrong)."""
        sp = self._sep
        sp["samples"] += 1
        if self.n < 2 or sp["samples"] % max(1, self.separation_every):
            return
        from .layout import min_separation
        d, pair = min_separation([st.position[:2] for st in self.states])
        if d < sp["min"]:
            sp["min"], sp["pair"] = d, pair
        sp["checks"] += 1
        if sp["checks"] % self.separation_window:
            return
        sp["window"] += 1
        msg = (f"[scensim] engine A: cars at least {sp['min']:.2f} m apart over policy steps "
               f"{sp['checks'] - self.separation_window}..{sp['checks'] - 1} (slots {sp['pair']})")
        print(msg + (f" WARNING: under {SEPARATION_WARN} m (issue 113)"
                     if sp["min"] < SEPARATION_WARN else ""), flush=True)
        m = self.landing_max
        m["separation_min"] = min(m.get("separation_min", math.inf), sp["min"])
        if sp["min"] < SEPARATION_WARN:
            import warnings
            warnings.warn(msg + f": under {SEPARATION_WARN} m (issue 113)", stacklevel=2)
        sp["min"], sp["pair"] = math.inf, None

    def _count_close(self):
        """Pairs of cars (of different envs: each env holds one) closer than CLOSE_M at this
        sample, counted over the run (`landing_max`), each new pair logged once (issue 113: cars
        of different envs passing through each other, if their collisions are not filtered)."""
        import json
        xy = np.array([st.position[:2] for st in self.states], dtype=np.float64)
        d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
        pairs = list(zip(*np.nonzero(np.triu(d < CLOSE_M, 1))))
        m = self.landing_max
        m["close_samples"] = m.get("close_samples", 0) + len(pairs)
        seen = self.__dict__.setdefault("_close_seen", set())
        for a, b in pairs:
            if (a, b) not in seen:
                seen.add((a, b))
                m["close_pairs"] = m.get("close_pairs", 0) + 1
                self.landing_log.write(json.dumps({"close": [int(a), int(b)], "d": round(float(
                    np.hypot(*(xy[a] - xy[b]))), 3)}) + "\n")

    def _usd_velocity(self, i):
        """Slot i's body velocity attributes as USD holds them (world (x, y) m/s, yaw rate deg/s,
        USD's unit): beside PhysX's, whether a reset's writes reached USD and PhysX alike."""
        from pxr import UsdPhysics
        body = UsdPhysics.RigidBodyAPI(self.stage.GetPrimAtPath(self.cars[i].path))
        lin, ang = body.GetVelocityAttr().Get(), body.GetAngularVelocityAttr().Get()
        return [None if lin is None else [round(float(lin[0]), 4), round(float(lin[1]), 4)],
                None if ang is None else round(float(ang[2]), 4)]

    def open_landing_log(self, path):
        """Every reset's landing to `path` (jsonl), after a header line with the physics settings
        that decide whether PhysX writes its velocities back to USD (issue 113)."""
        import json
        import carb
        st = carb.settings.get_settings()
        keys = ("/physics/updateToUsd", "/physics/updateVelocitiesToUsd",
                "/physics/outputVelocitiesLocalSpace", "/physics/fabricEnabled")
        self.landing_log = open(path, "a")
        self.landing_log.write(json.dumps({"settings": {k: st.get(k) for k in keys},
                                           "n": self.n, "groups": self.collision_groups()}) + "\n")
        self.landing_log.flush()

    def collision_groups(self, slots=None):
        """Which of Isaac Lab's per-env collision groups (/World/collisions, inverted filtering:
        cars of different groups do not collide) hold each car's colliders (243, issue 113): for
        `slots` (default the first two and the last), each collider prim of the car and the
        groups whose colliders collection includes it. A car in no group, or in another env's,
        collides with other envs' cars."""
        from pxr import Usd, UsdPhysics
        root = self.stage.GetPrimAtPath("/World/collisions")
        out = {"exists": bool(root and root.IsValid())}
        scene = [p for p in self.stage.Traverse() if p.IsA(UsdPhysics.Scene)]
        if scene:
            a = scene[0].GetAttribute("physxScene:invertCollisionGroupFilter")
            out["invert"] = a.Get() if a and a.IsValid() else None
        if not out["exists"]:
            return out
        groups = []
        for g in root.GetChildren():
            col = Usd.CollectionAPI(g, "colliders")
            groups.append((g.GetName(), col.ComputeMembershipQuery()))
        out["n_groups"] = len(groups)
        slots = slots if slots is not None else sorted({0, min(1, self.n - 1), self.n - 1})
        for i in slots:
            car = self.stage.GetPrimAtPath(self.cars[i].path)
            cols = [p for p in Usd.PrimRange(car) if p.HasAPI(UsdPhysics.CollisionAPI)]
            out[f"slot{i}"] = {str(p.GetPath()).rsplit("/", 1)[-1]:
                               [n for n, q in groups if q.IsPathIncluded(p.GetPath())]
                               for p in cols}
        return out

    def _local(self, i, p):
        """A world position in slot i's env prim's frame (its parent; translated, never rotated)."""
        return tuple(float(a - b) for a, b in zip(p, self.parent[i]))

    def apply(self, act, velocity=None, gear=None):
        """The coming step's actuation, with each request's velocity and gear for aib's
        sticky-tire release (core.request_motion); without them, 0 and drive, which holds a
        car whose request is to stop."""
        from sim_vehicle_ecu.signals import GEAR_DRIVE
        self.act = act
        self.velocity = np.zeros(self.n) if velocity is None else np.asarray(velocity, float)
        self.gear = (np.full(self.n, GEAR_DRIVE) if gear is None else np.asarray(gear))

    def advance(self, dt):
        """actuate, the world's step, sample: for a host that leaves the physics to us."""
        import time
        t0 = time.perf_counter()
        self.actuate(dt)
        t1 = time.perf_counter()
        self.world.step(render=False)
        t2 = time.perf_counter()
        self.sample(dt)
        t3 = time.perf_counter()
        tm = self.timing   # where a step's time goes (K2.5's split)
        tm["actuate"] += t1 - t0
        tm["physics"] += t2 - t1
        tm["sample"] += t3 - t2
        tm["steps"] += 1

    def actuate(self, dt):
        """Every car's actuation for the coming physics step (a host that owns the loop calls
        this, steps the engine, then sample)."""
        from sim_vehicle_ecu.signals import Actuation
        a = self.act
        drive, brake = np.asarray(a["drive"]), np.asarray(a["brake"])
        angle = np.asarray(a["tire_angle"])
        for i, (car, st) in enumerate(zip(self.cars, self.states)):
            car.actuate(Actuation(tuple(drive[i].tolist()), tuple(brake[i].tolist()),
                                  float(angle[i]), None), dt, st,
                        float(self.velocity[i]), int(self.gear[i]))

    def sample(self, dt):
        """Every car read back after a physics step."""
        for car, st in zip(self.cars, self.states):
            car.sample(self.physx, dt, st)
        self._separation()
        if self.landing_log is not None and \
                self._sep["samples"] % max(1, self.separation_every) == 0:
            self._count_close()      # once a policy step, as the separation
        if self._landing:
            self._check_landing(dt)
        if len(self.trace) < self.trace_steps:
            self.trace.append(self.readback(0))

    def readback(self, i):
        """Slot i after a physics step, as PhysX holds it (not USD): per wheel the steer angle,
        the spin and the tire's longitudinal force, beside what the component asked for. PhysX
        reports no drive or brake torque; the force and spin are their effect."""
        from omni.physx.bindings._physx import (VEHICLE_WHEEL_STATE_IS_ON_GROUND,
                                                VEHICLE_WHEEL_STATE_ROTATION_SPEED,
                                                VEHICLE_WHEEL_STATE_STEER_ANGLE,
                                                VEHICLE_WHEEL_STATE_TIRE_FORCE,
                                                VEHICLE_WHEEL_STATE_TIRE_LONGITUDINAL_DIRECTION)
        a = self.act
        row = {"asked_drive": np.asarray(a["drive"])[i].tolist(),
               "asked_brake": np.asarray(a["brake"])[i].tolist(),
               "asked_tire_angle": float(np.asarray(a["tire_angle"])[i]),
               "on_ground": [], "steer": [], "spin": [], "tire_fx": []}
        for wp in self.cars[i].wheel_paths:
            w = self.physx.get_wheel_state(wp)
            f = w[VEHICLE_WHEEL_STATE_TIRE_FORCE]
            d = w[VEHICLE_WHEEL_STATE_TIRE_LONGITUDINAL_DIRECTION]
            row["on_ground"].append(bool(w[VEHICLE_WHEEL_STATE_IS_ON_GROUND]))
            row["steer"].append(float(w[VEHICLE_WHEEL_STATE_STEER_ANGLE]))
            row["spin"].append(float(w[VEHICLE_WHEEL_STATE_ROTATION_SPEED]))
            row["tire_fx"].append(float(sum(float(x) * float(y) for x, y in zip(f, d))))
        return row

    def state(self):
        n = self.n
        x, y, yaw, v = (np.zeros(n) for _ in range(4))
        yr, ax, ay = (np.zeros(n) for _ in range(3))
        ws = np.zeros((n, 4))
        for i, (car, st) in enumerate(zip(self.cars, self.states)):
            px, py, _ = st.position
            w, qx, qy, qz = st.quat
            x[i], y[i] = px - self.origins[i][0], py - self.origins[i][1]
            yaw[i] = math.atan2(2 * (w * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
            v[i] = st.velocity[0]
            yr[i], ax[i], ay[i] = st.angular_velocity[2], st.acceleration[0], st.acceleration[1]
            if car.wheel_states is not None:
                ws[i] = [w_.rotation_speed for w_ in car.wheel_states]
        t = lambda a: torch.as_tensor(a, dtype=torch.float64)   # noqa: E731
        return {"x": t(x), "y": t(y), "yaw": t(yaw), "v": t(v), "yaw_rate": t(yr),
                "accel_x": t(ax), "accel_y": t(ay), "wheel_speeds": t(ws)}
