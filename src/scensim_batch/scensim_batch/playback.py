"""A backend that plays a recorded ego back instead of simulating one (roadmap 092 K10's agreement).

The batch's ego normally comes from an engine (A, aib's PhysX vehicle; B, an articulation).
For K10's walker agreement the seats ego is CARLA's car, which no engine reproduces, and a
walker deciding on its gap to the ego would see a different gap. So the batch plays back the
seats ego's truth, frame for frame, and everything else (the models, SSv2's default vehicles,
the storyboard) runs as in any batch: no engine is in that comparison.

    backend = TruthPlayback(states)       # states[k]: the ego at batch step k, after reset k=0
    run = BatchRun(compiled, world, backend, NoComponent.batch(...), ...)

Each state is a dict with x, y, yaw (the map frame, rad), vx_map, vy_map (m/s, the map frame:
what the seats attachment reads from the truth) and optionally v (along the body; default the
speed). `reset` goes to state 0 and `advance` one state on, holding the last; every slot plays
the same states. The actuation is taken and dropped.
"""
import math

import numpy as np
import torch


class TruthPlayback:
    def __init__(self, states, n=1):
        if not states:
            raise ValueError("TruthPlayback: no states to play")
        self.states, self.n, self.k = list(states), n, 0
        self.dt = None

    def reset(self, mask, x, y, yaw, speed):
        self.k = 0

    def apply(self, act, velocity=None, gear=None):
        pass

    def advance(self, dt):
        self.k = min(self.k + 1, len(self.states) - 1)
        self.dt = dt

    def state(self):
        s = self.states[self.k]
        prev = self.states[self.k - 1] if self.k > 0 else s
        dt = self.dt or 0.0
        vx, vy = float(s["vx_map"]), float(s["vy_map"])
        v = float(s["v"]) if s.get("v") is not None else math.hypot(vx, vy)
        ax = ay = yaw_rate = 0.0
        if dt > 0 and self.k > 0:
            c, sn = math.cos(s["yaw"]), math.sin(s["yaw"])
            dvx, dvy = (vx - prev["vx_map"]) / dt, (vy - prev["vy_map"]) / dt
            ax, ay = c * dvx + sn * dvy, -sn * dvx + c * dvy     # into the body frame
            yaw_rate = ((s["yaw"] - prev["yaw"] + math.pi) % (2 * math.pi) - math.pi) / dt
        f = lambda val: torch.full((self.n,), float(val), dtype=torch.float64)  # noqa: E731
        return {"x": f(s["x"]), "y": f(s["y"]), "yaw": f(s["yaw"]), "v": f(v),
                "yaw_rate": f(yaw_rate), "accel_x": f(ax), "accel_y": f(ay),
                "wheel_speeds": torch.zeros(self.n, 4, dtype=torch.float64),
                "vx_map": f(vx), "vy_map": f(vy)}


class NoComponentBatch:
    """The ego's component when nothing drives it: a vectorised autoware component that asks
    for nothing (the playback ignores the actuation anyway)."""
    commands = "autoware"
    truth = ()
    vectorised = True

    def __init__(self, vehicle, params, seeds):
        self.n = len(seeds)

    def reset_batch(self, mask):
        pass

    def step_batch(self, c, s, dt):
        z = np.zeros((self.n, 4))
        return {"drive": z, "brake": z.copy(), "tire_angle": np.zeros(self.n)}


class NoComponent:      # what sim_vehicle_ecu's load_batch resolves: a class declaring its batch
    batch = NoComponentBatch
