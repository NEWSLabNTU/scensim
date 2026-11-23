"""A CPU ego for the batch (roadmap 092, "K11c's spec, completed"): a point mass, its component,
and `aeb_ttc`, the invented emergency-braking ego K11c's search runs against.

- `PointMass` (a backend): a mass along its heading, its wheels at one radius, no steering, no
  tyres; the batch tests' stand-in, promoted. It is neither engine A (aib's PhysX vehicle) nor B
  (the articulation), and results run on it say so.
- `Accel` (a component, sim_vehicle_ecu's load_batch resolves its `batch`): the requested
  acceleration as rear-wheel torque, so the point mass accelerates exactly as asked.
- `AebTtc`: holds the ego's initial speed (acceleration 0) until its time to collision with the
  walker falls below `ttc` (1.5 s), then brakes at `decel` (6 m/s^2) to a stop, and keeps
  braking. The time to collision is the box-to-box gap along the ego's heading over its speed,
  counted while the walker's box overlaps the ego's corridor (its width); the walker's own
  motion is not predicted. INVENTED: both numbers are ours, not a fitted or a standard
  system's. The poses it reads are the entities' (the batch's own state, issue 130's frame).
"""
import math

import numpy as np
import torch

RADIUS, MASS = 0.35, 1800.0       # the point mass's wheel radius (m) and mass (kg)
TTC, DECEL = 1.5, 6.0             # aeb_ttc's threshold (s) and braking (m/s^2): invented


class PointMass:
    """The backend: N point masses (x, y, yaw, v), each along its heading."""

    def __init__(self, n):
        z = torch.zeros(n, dtype=torch.float64)
        self.x, self.y, self.yaw, self.v, self.ax = (z.clone() for _ in range(5))
        self.force = z.clone()

    def reset(self, mask, x, y, yaw, speed):
        for name, val in (("x", x), ("y", y), ("yaw", yaw), ("v", speed)):
            setattr(self, name, torch.where(mask, val, getattr(self, name)))
        self.ax = torch.where(mask, torch.zeros_like(self.ax), self.ax)

    def apply(self, act, velocity=None, gear=None):
        drive = torch.as_tensor(act["drive"], dtype=torch.float64).sum(-1)
        brake = torch.as_tensor(act["brake"], dtype=torch.float64).sum(-1)
        self.force = (drive - brake * torch.sign(self.v)) / RADIUS

    def advance(self, dt):
        self.ax = self.force / MASS
        self.v = torch.clamp(self.v + self.ax * dt, min=0.0)
        self.x = self.x + self.v * torch.cos(self.yaw) * dt
        self.y = self.y + self.v * torch.sin(self.yaw) * dt

    def state(self):
        w = (self.v / RADIUS)[:, None].expand(-1, 4)
        z = torch.zeros_like(self.v)
        return {"x": self.x, "y": self.y, "yaw": self.yaw, "v": self.v, "yaw_rate": z,
                "accel_x": self.ax, "accel_y": z, "wheel_speeds": w}


class AccelBatch:
    """The component: the requested acceleration as rear-wheel torque (drive or brake)."""
    commands = "autoware"
    truth = ()

    def __init__(self, vehicle, params, seeds):
        self.n = len(seeds)

    def reset_batch(self, mask):
        pass

    def step_batch(self, c, s, dt):
        a = np.where(c["valid"], c["acceleration"], 0.0)
        torque = a * MASS * RADIUS
        drive = np.zeros((self.n, 4))
        brake = np.zeros((self.n, 4))
        drive[:, 2] = drive[:, 3] = np.where(torque > 0, torque / 2, 0.0)
        brake[:, 2] = brake[:, 3] = np.where(torque < 0, -torque / 2, 0.0)
        return {"drive": drive, "brake": brake, "tire_angle": np.zeros(self.n)}


class Accel:   # what load_batch resolves: a class declaring its batch
    batch = AccelBatch


def commands(acceleration):
    """The component's command dict for accelerations [N]."""
    a = np.asarray(acceleration, dtype=float)
    n = len(a)
    return {"acceleration": a, "velocity": np.zeros(n), "tire_angle": np.zeros(n),
            "gear": np.full(n, 2, dtype=np.int64), "valid": np.ones(n, bool)}


def ttc(ego, walker, v):
    """The time to collision (s) of each slot, inf where the walker is not in the ego's
    corridor or is behind its front, 0 where the boxes already overlap along the corridor.
    `ego`, `walker`: (x, y, yaw, cx, length, width) arrays [N]; `v` the ego's speed [N]."""
    ex, ey, eyaw, ecx, el, ew = ego
    wx, wy, wyaw, wcx, wl, ww = walker
    hx, hy = np.cos(eyaw), np.sin(eyaw)
    # the boxes' centres
    ecx_w, ecy_w = ex + ecx * hx, ey + ecx * hy
    wcx_w, wcy_w = wx + wcx * np.cos(wyaw), wy + wcx * np.sin(wyaw)
    dx, dy = wcx_w - ecx_w, wcy_w - ecy_w
    along, across = dx * hx + dy * hy, -dx * hy + dy * hx
    d = wyaw - eyaw
    # the walker box's half extents along and across the ego's heading
    w_along = np.abs(wl / 2 * np.cos(d)) + np.abs(ww / 2 * np.sin(d))
    w_across = np.abs(wl / 2 * np.sin(d)) + np.abs(ww / 2 * np.cos(d))
    in_corridor = np.abs(across) <= ew / 2 + w_across
    gap = along - el / 2 - w_along
    behind = along + w_along < -el / 2
    out = np.full(len(v), math.inf)
    moving = v > 1e-9
    hit = in_corridor & ~behind
    out = np.where(hit & (gap <= 0), 0.0, out)
    ahead = hit & (gap > 0) & moving
    out = np.where(ahead, gap / np.where(moving, v, 1.0), out)
    return out


class AebTtc:
    """aeb_ttc over a BatchRun's observation: one acceleration per slot a step."""

    name = "aeb_ttc"

    def __init__(self, run, walker, ttc_s=TTC, decel=DECEL):
        c = run.c
        self.run, self.ego, self.walker = run, run.ego, walker
        self.ttc_s, self.decel = ttc_s, decel
        e, w = c.entities[run.ego], c.entities[walker]
        self.ebox = (e.cx, e.length, e.width)
        self.wbox = (w.cx, w.length, w.width)
        self.braking = np.zeros(c.n, bool)

    def reset(self, mask=None):
        mask = np.ones(len(self.braking), bool) if mask is None else np.asarray(mask, bool)
        self.braking[mask] = False

    def __call__(self, obs):
        col = lambda k, i: obs[k][:, i].detach().cpu().numpy().astype(float)   # noqa: E731
        n = len(self.braking)
        v = col("v", self.ego)
        ego = (col("x", self.ego), col("y", self.ego), col("yaw", self.ego),
               *(np.full(n, float(b)) for b in self.ebox))
        walker = (col("x", self.walker), col("y", self.walker), col("yaw", self.walker),
                  *(np.full(n, float(b)) for b in self.wbox))
        self.braking |= ttc(ego, walker, v) < self.ttc_s
        a = np.where(self.braking & (v > 0), -self.decel, 0.0)
        return commands(a)
