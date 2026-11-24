"""The gap-acceptance walker (roadmap 092 K10, scenario CS1): a pedestrian at a kerb who
crosses in front of the ego when the gap it is offered is acceptable.

The decision is a binary logit per presented gap (parameter set `khaki2021_restricted` by
default: Khaki and Mohammadnazar 2021, Table 3). The ego offers the gap when the walker first
decides: its time to the conflict point, ((c - p) . v) / (v . v), is the GAP. LAG is 1 (the
first vehicle's gap). The walker accepts when U > logit(u), where u is the walker's uniform
draw for the episode; that is the same event as u < P = 1 / (1 + exp(-U)). The draw and its
logit are taken once per walker at reset, on the host (`random.Random(seed)`, `math.log`; or
the parameter `draw`, u itself, when given: 092 K11d), so
the per-step path is only + - * /, comparisons and where. That path is one code over
sim_vehicle_ecu.xp, and its numpy and torch forms agree bit for bit.

Before it decides, a walker may be out of sight (CS1's walker behind the van). With
`start_gap`, it waits there until the ego's time to the conflict point falls to `start_gap`
(CS1's start trigger, `ttc_entry`, as a parameter the sampler binds). It then walks `approach`
metres toward the kerb edge at its speed, and decides where it can still stop at the kerb,
speed^2 / (2 accel_limit) before it (a walker judges the gap on the way). The decision then sees
the gap at that point, not at the start. Without `start_gap`, it starts walking (or, with no `approach`,
decides) at the first step. Positions along the crossing are measured from the kerb edge, so
the hidden spot is at -approach.

A walker that rejects waits until the ego has passed the conflict point, then crosses, since
no other vehicle offers a gap in CS1. Its styles:
- `steady` crosses at its speed;
- `run` crosses at `run_factor` times it;
- `hesitate` stops at the lane edge (`hesitate_at` m along the crossing) if the ego is then
  closer than `abort_gap` s, and resumes once it has passed.
`run_factor`, `hesitate_at`, `abort_gap` and `yield_decel` are ours, not the paper's
(params_schema marks them).

Per step, `obs` holds arrays over slots:
- `x`, `y`: the walker's own position, from the world;
- `ego_x`, `ego_y`, `ego_vx`, `ego_vy`, `ego_ax`, `ego_ay`: the ego's truth, in the map frame;
- `valid`: False where a slot has no reading this step.
`anchors` give each slot's crossing: `kerb` (where it waits), `far` (the other side) and
`conflict` (the point the ego's path crosses), each as [x, y] in the map frame.
`step` returns the action (`speed`, `heading`, `accel_limit`, per slot) and the events of this
step (an int per slot, `EVENTS`).
"""
import math
import random

# one event per slot and step; reaching the kerb is the decision's step, so it has none of its own
EVENTS = {0: "none", 1: "go", 2: "reject", 3: "go_after", 4: "hesitate", 5: "resume", 6: "done",
          7: "appear"}
GO, REJECT, GO_AFTER, HESITATE, RESUME, DONE, APPEAR = 1, 2, 3, 4, 5, 6, 7
# phases
UNDECIDED, WAITING, CROSSING, HELD, CROSSED, HIDDEN, APPROACH = 0, 1, 2, 3, 4, 5, 6
STYLES = ("steady", "run", "hesitate")
EPS_VV = 1e-6           # (m/s)^2: below it the ego is at rest and offers no gap

# name: (type, default, (min, max) or choices, the source: "set" (the paper's variable) or "ours")
PARAMS = {
    "parameter_set": (str, "khaki2021_restricted", None, "the set's file"),
    "speed":         (float, 1.4, (0.5, 3.0), "PS: walking speed, m/s"),
    "style":         (str, "steady", STYLES, "ours"),
    "group":         (bool, False, None, "GR: crossing in a group"),
    "rolling_gap":   (bool, False, None, "ROLL: uses rolling gaps"),
    "lag":           (bool, True, None, "LAG: the gap is the first vehicle's"),
    "lane":          (int, 1, (1, 3), "LANE: the conflict's lane, 1 near"),
    "conflict_rate": (float, None, (0.0, 5.0), "RATE: veh/s/ln; default the set's sample mean"),
    "yield_decel":   (float, 0.5, (0.0, 10.0), "ours: the ego's deceleration, m/s^2, read as YIELD"),
    "run_factor":    (float, 1.5, (1.0, 3.0), "ours: run speed over walking speed"),
    "hesitate_at":   (float, 0.5, (0.0, 10.0), "ours: m along the crossing where hesitate re-checks"),
    "abort_gap":     (float, 1.5, (0.0, 10.0), "ours: s; a closer ego there holds the walker"),
    "accel_limit":   (float, 1.5, (0.1, 10.0), "ours: m/s^2, the world's limit on the command"),
    "start_gap":     (float, None, (0.0, 30.0), "the scenario's: s; hidden until the ego is this "
                                                "close in time (CS1's ttc_entry)"),
    "approach":      (float, 0.0, (0.0, 20.0), "the scenario's: m walked to the kerb before "
                                               "deciding"),
    "draw":          (float, None, (0.0, 1.0), "ours: the episode's uniform draw u, given "
                                               "(092 K11d); default: from the seed"),
}


def resolve(params: dict) -> dict:
    """`params` checked against PARAMS, with the defaults filled in. Refuses an unknown name, a
    wrong type and a value out of range, by name."""
    out = {}
    for k in params:
        if k not in PARAMS:
            raise ValueError(f"gap_acceptance_walker: unknown parameter {k!r} "
                             f"(known: {', '.join(PARAMS)})")
    for k, (typ, default, rng, _) in PARAMS.items():
        v = params.get(k, default)
        if v is None:
            out[k] = None
            continue
        if typ is bool:
            if isinstance(v, str) and v.lower() in ("true", "false"):
                v = v.lower() == "true"
            if not isinstance(v, bool):
                raise ValueError(f"gap_acceptance_walker: {k}: {v!r} is not true or false")
        elif typ in (int, float):
            if isinstance(v, bool):
                raise ValueError(f"gap_acceptance_walker: {k}: {v!r} is not a number")
            v = typ(float(v)) if typ is float else int(v)
            if rng is not None and not (rng[0] <= v <= rng[1]):
                raise ValueError(f"gap_acceptance_walker: {k}: {v} outside [{rng[0]}, {rng[1]}]")
        else:
            v = str(v)
            if rng is not None and v not in rng:
                raise ValueError(f"gap_acceptance_walker: {k}: {v!r} not one of {', '.join(rng)}")
        out[k] = v
    return out


class GapAcceptanceWalker:
    array_api = ("numpy", "torch")
    name = "gap_acceptance_walker"
    params_schema = PARAMS
    events = EVENTS

    def __init__(self, params, seeds, anchors, xp):
        from . import parameter_set

        n = len(params)
        if len(seeds) != n or len(anchors) != n:
            raise ValueError(f"gap_acceptance_walker: {n} params, {len(seeds)} seeds, "
                             f"{len(anchors)} anchors")
        self.xp, self.n = xp, n
        self.params = [resolve(p) for p in params]
        names = {p["parameter_set"] for p in self.params}
        self.sets = {s: parameter_set(s) for s in names}
        self._anchors = [dict(a) for a in anchors]
        self._host = [self._slot_constants(p, a) for p, a in zip(self.params, self._anchors)]
        col = lambda key: xp.asarray([h[key] for h in self._host], xp.float64)  # noqa: E731
        self.kx, self.ky, self.dx, self.dy = col("kx"), col("ky"), col("dx"), col("dy")
        self.cx, self.cy, self.length = col("cx"), col("cy"), col("length")
        self.heading, self.cross_speed = col("heading"), col("cross_speed")
        self.base, self.c_gap, self.c_time = col("base"), col("c_gap"), col("c_time")
        self.c_yield, self.yd2 = col("c_yield"), col("yd2")
        self.hesitate_at, self.abort_gap = col("hesitate_at"), col("abort_gap")
        self.accel_limit = col("accel_limit")
        self.hesitates = xp.asarray([p["style"] == "hesitate" for p in self.params], xp.bool)
        self.start_gap = col("start_gap")
        self.walk_speed = col("walk_speed")
        self.decide_at = col("decide_at")
        self.phase0 = xp.asarray([h["phase0"] for h in self._host], xp.int64)
        self.threshold = xp.zeros(n)          # logit(u), per episode
        self.phase = xp.zeros(n, xp.int64)
        self.wait_t = xp.zeros(n)
        self.rechecked = xp.zeros(n, xp.bool)
        self.decision_gap = xp.full(n, xp.nan)  # the GAP offered at the decision, s
        self.decision_u = xp.full(n, xp.nan)    # U at the decision
        self.seeds = [int(s) for s in seeds]
        self.reset(None, self.seeds)

    def _slot_constants(self, p: dict, a: dict) -> dict:
        s = self.sets[p["parameter_set"]]
        b = {k: float(v["beta"]) for k, v in s["coefficients"].items()}
        (kx, ky), (fx, fy), (cx, cy) = a["kerb"], a["far"], a["conflict"]
        length = math.hypot(fx - kx, fy - ky)
        if length <= 0.0:
            raise ValueError("gap_acceptance_walker: kerb and far are the same point")
        rate = p["conflict_rate"]
        if rate is None:
            rate = float(s["ranges"]["RATE"]["mean"])
        # the per-slot constant part of U, in the paper's order (equation 2), on the host
        base = b["intercept"] + b["PS"] * p["speed"] + b["GR"] * float(p["group"])
        base = base + b["ROLL"] * float(p["rolling_gap"]) + b["LAG"] * float(p["lag"])
        base = base + b["LANE"] * float(p["lane"]) + b["RATE"] * rate
        factor = p["run_factor"] if p["style"] == "run" else 1.0
        return dict(kx=kx, ky=ky, dx=(fx - kx) / length, dy=(fy - ky) / length, cx=cx, cy=cy,
                    length=length, heading=math.atan2(fy - ky, fx - kx),
                    cross_speed=p["speed"] * factor, base=base, c_gap=b["GAP"],
                    c_time=b["TIME"], c_yield=b["YIELD"], yd2=p["yield_decel"] ** 2,
                    hesitate_at=p["hesitate_at"], abort_gap=p["abort_gap"],
                    accel_limit=p["accel_limit"], rate=rate,
                    start_gap=-1.0 if p["start_gap"] is None else p["start_gap"],
                    walk_speed=p["speed"],
                    decide_at=-(p["speed"] ** 2) / (2.0 * p["accel_limit"]),
                    phase0=(HIDDEN if p["start_gap"] is not None
                            else APPROACH if p["approach"] > 0.0 else UNDECIDED))

    @staticmethod
    def draw(seed: int, u=None) -> float:
        """A walker's draw for an episode, and its logit: the same on seats and in a batch.
        `u`: the draw given (the parameter `draw`, 092 K11d), else the seed's."""
        if u is None:
            u = random.Random(int(seed)).random()
        u = min(max(float(u), 1e-12), 1.0 - 1e-12)
        return math.log(u / (1.0 - u))

    def reset(self, mask=None, seeds=None):
        """Start an episode in the slots `mask` marks (None: all), with `seeds` (one per slot,
        or None to keep each slot's seed). The draws are taken here, on the host."""
        xp, n = self.xp, self.n
        if seeds is not None:
            for i, s in enumerate(seeds):
                if s is not None:
                    self.seeds[i] = int(s)
        idx = list(range(n)) if mask is None else [int(i) for i in xp.nonzero(mask)]
        if not idx:
            return
        th = [float(x) for x in self.xp.to_host(self.threshold)]
        for i in idx:
            th[i] = self.draw(self.seeds[i], self.params[i]["draw"])
        self.threshold = xp.asarray(th, xp.float64)
        m = xp.ones(n, xp.bool) if mask is None else xp.asarray(mask, xp.bool)
        self.phase = xp.where(m, self.phase0, self.phase)
        self.wait_t = xp.where(m, xp.zeros(n), self.wait_t)
        self.rechecked = self.rechecked & ~m
        self.decision_gap = xp.where(m, xp.full(n, xp.nan), self.decision_gap)
        self.decision_u = xp.where(m, xp.full(n, xp.nan), self.decision_u)

    def step(self, obs: dict, dt: float):
        xp, n = self.xp, self.n
        valid = xp.asarray(obs["valid"], xp.bool)
        ex, ey = obs["ego_x"], obs["ego_y"]
        vx, vy = obs["ego_vx"], obs["ego_vy"]
        ax, ay = obs["ego_ax"], obs["ego_ay"]
        s = (obs["x"] - self.kx) * self.dx + (obs["y"] - self.ky) * self.dy
        rel = (self.cx - ex) * vx + (self.cy - ey) * vy           # > 0: the ego approaches
        vv = vx * vx + vy * vy
        moving = vv > EPS_VV
        approaching = moving & (rel > 0.0)
        gap = xp.where(approaching, rel / xp.where(moving, vv, xp.ones(n)), xp.zeros(n))
        av = ax * vx + ay * vy
        yielding = (av < 0.0) & (av * av > self.yd2 * vv)        # decelerating by > yield_decel
        u = self.base + self.c_gap * gap + self.c_time * self.wait_t
        u = u + self.c_yield * xp.where(yielding, xp.ones(n), xp.zeros(n))
        accept = (~approaching) | (u > self.threshold)
        ev = xp.zeros(n, xp.int64)
        ph = self.phase

        # out of sight until the ego is start_gap away in time, then walking to the kerb
        appear = valid & (ph == HIDDEN) & approaching & (gap <= self.start_gap)
        ev = xp.where(appear, xp.full(n, APPEAR, xp.int64), ev)
        ph = xp.where(appear, xp.full(n, APPROACH, xp.int64), ph)
        kerb = valid & (ph == APPROACH) & (s >= self.decide_at)
        ph = xp.where(kerb, xp.full(n, UNDECIDED, xp.int64), ph)

        decide = valid & (ph == UNDECIDED)
        self.decision_gap = xp.where(decide & approaching, gap, self.decision_gap)
        self.decision_u = xp.where(decide & approaching, u, self.decision_u)
        go = decide & accept
        rej = decide & ~accept
        ev = xp.where(go, xp.full(n, GO, xp.int64), ev)
        ev = xp.where(rej, xp.full(n, REJECT, xp.int64), ev)
        ph = xp.where(go, xp.full(n, CROSSING, xp.int64), ph)
        ph = xp.where(rej, xp.full(n, WAITING, xp.int64), ph)

        after = valid & (ph == WAITING) & ~rej & ~approaching      # the ego has passed
        ev = xp.where(after, xp.full(n, GO_AFTER, xp.int64), ev)
        ph = xp.where(after, xp.full(n, CROSSING, xp.int64), ph)

        check = valid & self.hesitates & (ph == CROSSING) & ~self.rechecked & \
            (s >= self.hesitate_at)
        hold = check & approaching & (gap < self.abort_gap)
        self.rechecked = self.rechecked | check
        ev = xp.where(hold, xp.full(n, HESITATE, xp.int64), ev)
        ph = xp.where(hold, xp.full(n, HELD, xp.int64), ph)
        resume = valid & (self.phase == HELD) & ~approaching
        ev = xp.where(resume, xp.full(n, RESUME, xp.int64), ev)
        ph = xp.where(resume, xp.full(n, CROSSING, xp.int64), ph)

        done = valid & (ph == CROSSING) & (s >= self.length)
        ev = xp.where(done, xp.full(n, DONE, xp.int64), ev)
        ph = xp.where(done, xp.full(n, CROSSED, xp.int64), ph)

        waiting = valid & ((ph == UNDECIDED) | (ph == WAITING) | (ph == HELD))
        self.wait_t = xp.where(waiting, self.wait_t + dt, self.wait_t)
        self.phase = ph
        speed = xp.where(ph == CROSSING, self.cross_speed, xp.zeros(n))
        speed = xp.where(ph == APPROACH, self.walk_speed, speed)
        return {"speed": speed, "heading": self.heading, "accel_limit": self.accel_limit}, ev

    def record(self) -> list:
        """Per slot, what a run's record keeps: the model, its parameters and set (name and
        sha256), the seed and the draw's logit, the decision's gap and U, and P at it (computed
        here, on the host, for the record only)."""
        th = self.xp.to_host(self.threshold)
        dg = self.xp.to_host(self.decision_gap)
        du = self.xp.to_host(self.decision_u)
        out = []
        for i, p in enumerate(self.params):
            st = self.sets[p["parameter_set"]]
            u = float(du[i])
            out.append({
                "model": f"scensim.behaviour:{self.name}",
                "params": dict(p, conflict_rate=self._host[i]["rate"]),
                "parameter_set": {"name": st["name"], "sha256": st["sha256"],
                                  "source": st["source"]["id"]},
                "seed": self.seeds[i], "threshold_logit": float(th[i]),
                "decision": None if math.isnan(u) else {
                    "gap_s": float(dg[i]), "u": u, "p_accept": 1.0 / (1.0 + math.exp(-u))},
            })
        return out
