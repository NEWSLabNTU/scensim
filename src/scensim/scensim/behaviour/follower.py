"""The car-follower (roadmap 092 K13): a vehicle that holds one lane and follows the vehicle
ahead of it on that lane under the Intelligent Driver Model (Treiber, Hennecke and Helbing
2000; docs/design/vehicle-behaviour-model.md):

    a_idm  = a (1 - (v / v0)^4 - (s_star / s)^2)
    s_star = s0 + v T + v dv / (2 sqrt(a b))

v its speed along the lane, s the gap to its leader's rear, dv = v - v_leader. Its coefficients
s0, T, a and b come from a named, cited set (`zhang2024_highd_car` by default: motorway-fitted);
v0 is the lane's speed limit unless given. delta is 4, the set's, written as two squarings.

The deceleration is capped at the vehicle's `max_decel` (its catalog maxDeceleration). IDM's
freedom from collisions rests on its deceleration being unbounded, so a frame where the cap
binds is reported (`capped`): a collision of the model's own can only follow one.

**The lane.** `anchors` give each slot its lane, a resolved K9 lane anchor (`x`, `y`: the
centreline; `length`, `speed_limit`). On the host it is resampled every `DS` m of the spline's
s (its `heading_s`, the s the world places by; issue 166), extended straight past its end so the
arrays of every slot have one length; a point is placed on the lane by its nearest segment,
searched in a window around the last one (the whole lane the first time). The command's
heading is the segment's, corrected toward the centreline by -e / `LOOKAHEAD` (e the signed
lateral offset, clamped to +-`MAX_CORRECTION` rad): the world moves the vehicle along it, so it
keeps to the lane.

**The leader** is another entity's truth (`leader_*` in `obs`), placed on the same lane: it
leads when it is ahead and within `half_width` m of the centreline. Positions are entity
origins (a vehicle's rear axle, for SSv2); the gap runs from this vehicle's box front
(`center_x + length / 2` ahead of its origin) to the leader's box rear. The lane's end is a standing
obstacle: with no leader, or a farther one, the follower stops `s0` before it.

**The command** is K12's: `speed = max(0, v + a_cmd dt)` and `accel_limit = max(|a_cmd|,
MIN_ACCEL)`, so the world's integrator (`v += clamp(speed - v, +-accel_limit dt)`) applies
exactly a_cmd over the frame.

Per step, `obs` holds arrays over slots: `x`, `y`, `vx`, `vy` (its own truth, map frame),
`leader_x`, `leader_y`, `leader_vx`, `leader_vy`, `leader_valid` (False: no leader entity this
frame), and `valid` (False: no reading for the slot). Every operation of the step is one of
sim_vehicle_ecu.xp's (elementwise + - * /, sqrt, min, max, where, comparisons, and indexing by
integer arrays, which rounds nothing), so numpy and torch agree bit for bit.
"""
import math

# one event per slot and step
EVENTS = {0: "none", 1: "follow", 2: "free", 3: "capped", 4: "stopped", 5: "lost"}
FOLLOW, FREE, CAPPED, STOPPED, LOST = 1, 2, 3, 4, 5

DS = 0.5                # m: the lane's resampling step
WINDOW = 12             # segments searched each step, from one behind the last
LOOKAHEAD = 8.0         # m: the heading's correction toward the centreline, -e / LOOKAHEAD
MAX_CORRECTION = 0.3    # rad
MIN_ACCEL = 1e-3        # m/s^2: the command's accel_limit is never 0 (K12 D5 refuses it)
LOST_OFFSET = 4.0       # m: farther from the centreline, the vehicle has left its lane
STOP_SPEED = 0.05       # m/s: below it, stopped
EXTEND = 50.0           # m of straight lane past the anchor's end
MIN_GAP = 0.01          # m: a gap below it is taken as this (the cap binds)

# name: (type, default, (min, max) or None, the source: "set" or "ours" or the scenario's)
PARAMS = {
    "parameter_set": (str, "zhang2024_highd_car", None, "the set's file"),
    "lane":          (str, None, None, "the scenario's: the lane anchor it holds"),
    "leader":        (str, None, None, "the scenario's: the entity it follows (or none)"),
    "v0":            (float, None, (1.0, 70.0), "m/s; default the lane's speed limit"),
    "s0":            (float, None, (0.5, 8.0), "set: jam spacing, m"),
    "T":             (float, None, (0.3, 3.0), "set: time headway, s"),
    "a":             (float, None, (0.1, 4.0), "set: maximum acceleration, m/s^2"),
    "b":             (float, None, (0.5, 6.0), "set: comfortable deceleration, m/s^2"),
    "max_accel":     (float, 4.0, (0.1, 20.0), "the catalog's maxAcceleration, m/s^2"),
    "max_decel":     (float, 8.0, (0.5, 20.0), "the catalog's maxDeceleration, m/s^2"),
    "length":        (float, 4.5, (1.0, 25.0), "the catalog's bounding box length, m"),
    "center_x":      (float, 0.0, (-10.0, 10.0), "the box centre ahead of the entity origin, m"),
    "leader_length": (float, 4.5, (0.5, 25.0), "the leader's bounding box length, m"),
    "leader_center_x": (float, 0.0, (-10.0, 10.0), "the leader's box centre ahead of its origin"),
    "half_width":    (float, 1.75, (0.5, 5.0), "ours: m from the centreline a leader counts"),
}


def resolve(params: dict) -> dict:
    """`params` checked against PARAMS, with the defaults filled in. Refuses an unknown name, a
    wrong type and a value out of range, by name."""
    out = {}
    for k in params:
        if k not in PARAMS:
            raise ValueError(f"idm_follower: unknown parameter {k!r} (known: {', '.join(PARAMS)})")
    for k, (typ, default, rng, _) in PARAMS.items():
        v = params.get(k, default)
        if v is None:
            out[k] = None
            continue
        if typ is float:
            if isinstance(v, bool):
                raise ValueError(f"idm_follower: {k}: {v!r} is not a number")
            v = float(v)
            if rng is not None and not (rng[0] <= v <= rng[1]):
                raise ValueError(f"idm_follower: {k}: {v} outside [{rng[0]}, {rng[1]}]")
        else:
            v = str(v)
        out[k] = v
    if out["lane"] is None:
        raise ValueError("idm_follower: lane: the lane anchor it holds is required")
    return out


def centreline_of(lane: dict) -> dict:
    """{x, y}: a lane anchor's centreline from its start and its heading profile."""
    ss, hs = [float(v) for v in lane["heading_s"]], [float(v) for v in lane["heading"]]
    x, y = [float(lane["start_x"])], [float(lane["start_y"])]
    for i in range(1, len(ss)):
        d = ss[i] - ss[i - 1]
        a, b = hs[i - 1], hs[i]
        h = a + math.remainder(b - a, 2.0 * math.pi) / 2.0
        x.append(x[-1] + d * math.cos(h))
        y.append(y[-1] + d * math.sin(h))
    return {"x": x, "y": y}


def resample(lane: dict, ds: float = DS, extend: float = EXTEND):
    """The lane's centreline every `ds` m of the spline's s, extended straight `extend` m past
    its end: (xs, ys), on the host. The anchor's `x`/`y` are its spline sampled at `heading_s`,
    and point k is placed at s = k ds between the two samples around it, so a position read as
    (k + t) ds is in the spline's s, the s the world places by: across a reversed loop the
    polyline's own arc runs short of it (issue 166, "A placement s and a model's gap").
    Repeated `heading_s` values (the joins between lanelets) are zero-length steps and are
    dropped. An anchor without `heading_s` matching its points is resampled in polyline arc;
    one resolved before its centreline was recorded (K9 before cd65e4ce: `heading_s`,
    `heading`, `start_x`, `start_y` only) has it rebuilt from its headings, each interval along
    the mean of its two, and its `heading_s` then gives the s."""
    if "x" not in lane and "heading_s" in lane:
        lane = dict(lane, **centreline_of(lane))
    x, y = [float(v) for v in lane["x"]], [float(v) for v in lane["y"]]
    if len(x) < 2 or len(x) != len(y):
        raise ValueError("idm_follower: the lane anchor has no centreline (x, y)")
    hs = lane.get("heading_s")
    if hs is not None and len(hs) == len(x):
        u = [float(v) for v in hs]
    else:
        u = [0.0]
        for i in range(1, len(x)):
            u.append(u[-1] + math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]))
    kx, ky, cum = [x[0]], [y[0]], [u[0]]
    for i in range(1, len(x)):
        if u[i] < cum[-1] - 1e-6:
            raise ValueError(f"idm_follower: the lane anchor's heading_s goes back at point {i} "
                             f"({u[i]} after {cum[-1]})")
        if u[i] - cum[-1] > 1e-9:
            kx.append(x[i])
            ky.append(y[i])
            cum.append(u[i])
    x, y = kx, ky
    cum = [c - cum[0] for c in cum]
    total = cum[-1]
    if len(x) < 2 or total <= 0.0:
        raise ValueError("idm_follower: the lane anchor's centreline has no length")
    hx, hy = x[-1] - x[-2], y[-1] - y[-2]
    hn = math.hypot(hx, hy)
    xs, ys, j = [], [], 0
    n = int(math.floor((total + extend) / ds)) + 1
    for k in range(n):
        s = k * ds
        if s <= total:
            while j < len(cum) - 2 and cum[j + 1] < s:
                j += 1
            seg = cum[j + 1] - cum[j]
            t = 0.0 if seg <= 0.0 else (s - cum[j]) / seg
            xs.append(x[j] + t * (x[j + 1] - x[j]))
            ys.append(y[j] + t * (y[j + 1] - y[j]))
        else:
            xs.append(x[-1] + (s - total) * hx / hn)
            ys.append(y[-1] + (s - total) * hy / hn)
    return xs, ys


def lane_anchors(params: list, resolved: dict) -> list:
    """Per slot, the model's anchors: its `lane` from the map's resolved anchors (K9's
    anchors.resolved.json), refused by name when absent or not a lane."""
    out = []
    for p in params:
        name = p.get("lane")
        a = (resolved or {}).get(name)
        if a is None:
            raise ValueError(f"idm_follower: lane {name!r}: no such anchor on the map "
                             f"(known: {', '.join(sorted(resolved or {})) or 'none'})")
        if a.get("kind") != "lane":
            raise ValueError(f"idm_follower: lane {name!r} is a {a.get('kind')} anchor, not a lane")
        out.append({"lane": a})
    return out


def seats_obs(me, entities: dict, leader, np):
    """One slot's observation on seats: `me` and the leader's truth (x, y, yaw, vx, vy) from the
    frame's `entities` (the leader absent, or none: `leader_valid` False)."""
    a = lambda v: np.array([float(v)])   # noqa: E731
    lead = entities.get(leader) if leader else None
    ok = lead is not None
    lead = lead if ok else me
    return {"x": a(me[0]), "y": a(me[1]), "vx": a(me[3]), "vy": a(me[4]),
            "leader_x": a(lead[0]), "leader_y": a(lead[1]), "leader_vx": a(lead[3]),
            "leader_vy": a(lead[4]), "leader_valid": np.array([ok]), "valid": np.array([True])}


class IdmFollower:
    array_api = ("numpy", "torch")
    name = "idm_follower"
    params_schema = PARAMS
    events = EVENTS

    def __init__(self, params, seeds, anchors, xp):
        from . import parameter_set

        n = len(params)
        if len(seeds) != n or len(anchors) != n:
            raise ValueError(f"idm_follower: {n} params, {len(seeds)} seeds, {len(anchors)} anchors")
        self.xp, self.n = xp, n
        self.seeds = [int(s) for s in seeds]   # unused: the model draws nothing
        self.params = [resolve(p) for p in params]
        self.sets = {s: parameter_set(s) for s in {p["parameter_set"] for p in self.params}}
        self._anchors = [dict(a) for a in anchors]
        self._host = [self._slot_constants(p, a) for p, a in zip(self.params, self._anchors)]
        col = lambda key: xp.asarray([h[key] for h in self._host], xp.float64)  # noqa: E731
        self.v0, self.s0, self.T, self.a = col("v0"), col("s0"), col("T"), col("a")
        self.two_sqrt_ab = col("two_sqrt_ab")
        self.max_accel, self.max_decel = col("max_accel"), col("max_decel")
        self.front, self.lead_rear = col("front"), col("lead_rear")
        self.end_s, self.half_width = col("end_s"), col("half_width")
        # the lanes, every slot's resampled to one length (K points, K - 1 segments)
        k = max(len(h["xs"]) for h in self._host)
        pad = lambda v, k: v + [v[-1] + (i + 1) * (v[-1] - v[-2]) for i in range(k - len(v))]  # noqa: E731
        xs = [pad(h["xs"], k) for h in self._host]
        ys = [pad(h["ys"], k) for h in self._host]
        self.K = k
        self.X = xp.asarray(xs, xp.float64)
        self.Y = xp.asarray(ys, xp.float64)
        # each segment's direction and squared length, and its heading (on the host: atan2)
        dx = [[r[i + 1] - r[i] for i in range(k - 1)] + [r[-1] - r[-2]] for r in xs]
        dy = [[r[i + 1] - r[i] for i in range(k - 1)] + [r[-1] - r[-2]] for r in ys]
        self.DX, self.DY = xp.asarray(dx, xp.float64), xp.asarray(dy, xp.float64)
        self.L2 = self.DX * self.DX + self.DY * self.DY
        self.UX = xp.asarray([[a / math.hypot(a, b) for a, b in zip(ra, rb)]
                              for ra, rb in zip(dx, dy)], xp.float64)
        self.UY = xp.asarray([[b / math.hypot(a, b) for a, b in zip(ra, rb)]
                              for ra, rb in zip(dx, dy)], xp.float64)
        self.H = xp.asarray([[math.atan2(b, a) for a, b in zip(ra, rb)]
                             for ra, rb in zip(dx, dy)], xp.float64)
        self.rows = xp.index(list(range(n)))
        # a slot without a leader is never searched for one
        self.no_leader = xp.asarray([p["leader"] is None for p in self.params], xp.bool)
        self.reset()

    def _slot_constants(self, p: dict, a: dict) -> dict:
        st = self.sets[p["parameter_set"]]
        c = {k: float(v) for k, v in st["coefficients"].items()}
        if c.get("delta") != 4.0:
            raise ValueError(f"idm_follower: set {st['name']}: delta {c.get('delta')}, not 4")
        lane = a.get("lane")
        if not isinstance(lane, dict):
            raise ValueError(f"idm_follower: no lane anchor {p['lane']!r} in the anchors")
        v0 = p["v0"] if p["v0"] is not None else float(lane["speed_limit"])
        s0, T = p["s0"] if p["s0"] is not None else c["s0"], p["T"] if p["T"] is not None else c["T"]
        aa, bb = p["a"] if p["a"] is not None else c["a"], p["b"] if p["b"] is not None else c["b"]
        if aa > p["max_accel"]:
            raise ValueError(f"idm_follower: a {aa} above the vehicle's max_accel {p['max_accel']}")
        if bb > p["max_decel"]:
            raise ValueError(f"idm_follower: b {bb} above the vehicle's max_decel {p['max_decel']}")
        xs, ys = resample(lane)
        return dict(v0=v0, s0=s0, T=T, a=aa, b=bb, two_sqrt_ab=2.0 * math.sqrt(aa * bb),
                    max_accel=p["max_accel"], max_decel=p["max_decel"],
                    front=p["center_x"] + 0.5 * p["length"],
                    lead_rear=p["leader_center_x"] - 0.5 * p["leader_length"],
                    end_s=float(lane["length"]), half_width=p["half_width"], xs=xs, ys=ys)

    def reset(self, mask=None, seeds=None):
        """Start an episode in the slots `mask` marks (None: all): the next step places the
        vehicle and its leader on the lane by a search of the whole lane."""
        xp, n = self.xp, self.n
        if seeds is not None:
            for i, s in enumerate(seeds):
                if s is not None:
                    self.seeds[i] = int(s)
        m = xp.ones(n, xp.bool) if mask is None else xp.asarray(mask, xp.bool)
        z = xp.zeros(n, xp.int64)
        f = xp.zeros(n, xp.bool)
        self.k_self = z if mask is None else xp.where(m, z, self.k_self)
        self.k_lead = z if mask is None else xp.where(m, z, self.k_lead)
        self.placed = f if mask is None else self.placed & ~m
        self.lead_placed = self.no_leader | (f if mask is None else self.lead_placed & ~m)
        self.following = f if mask is None else self.following & ~m
        self.stopped = f if mask is None else self.stopped & ~m
        self.lost = f if mask is None else self.lost & ~m
        # host flags: every slot placed (then no whole-lane search, and no sync to ask)
        self._all_placed = self._all_lead_placed = False

    def _seg(self, A, k):
        return A[self.rows, k]

    def _nearest(self, px, py, k0, start, count):
        """The nearest segment to (px, py) among `count` from `k0 + start` (clipped to the
        lane): (k, t, d2), t its fraction, d2 the squared distance. Ties keep the first."""
        xp = self.xp
        best_k, best_t, best_d = k0, xp.zeros(self.n), xp.full(self.n, math.inf)
        for j in range(count):
            k = xp.minimum(xp.maximum(k0 + (start + j), xp.zeros(self.n, xp.int64)),
                           xp.full(self.n, self.K - 2, xp.int64))
            ax, ay = self._seg(self.X, k), self._seg(self.Y, k)
            dx, dy, l2 = self._seg(self.DX, k), self._seg(self.DY, k), self._seg(self.L2, k)
            t = ((px - ax) * dx + (py - ay) * dy) / l2
            t = xp.minimum(xp.maximum(t, xp.zeros(self.n)), xp.ones(self.n))
            qx, qy = ax + t * dx - px, ay + t * dy - py
            d = qx * qx + qy * qy
            better = d < best_d
            best_k = xp.where(better, k, best_k)
            best_t = xp.where(better, t, best_t)
            best_d = xp.where(better, d, best_d)
        return best_k, best_t, best_d

    def _place(self, px, py, k_last, placed, all_placed):
        """(k, s, e, ux, uy): the segment, the arc position, the signed lateral offset (left
        positive) and the lane's direction there. A slot not yet placed is searched over the
        whole lane, the others in the window; `all_placed` (a host flag) skips the whole-lane
        search once every slot is placed."""
        xp = self.xp
        kw, tw, _ = self._nearest(px, py, k_last, -1, WINDOW)
        if all_placed:
            k, t = kw, tw
        else:
            kg, tg, _ = self._nearest(px, py, xp.zeros(self.n, xp.int64), 0, self.K - 1)
            k, t = xp.where(placed, kw, kg), xp.where(placed, tw, tg)
        ux, uy = self._seg(self.UX, k), self._seg(self.UY, k)
        ax, ay = self._seg(self.X, k), self._seg(self.Y, k)
        rx, ry = px - ax, py - ay
        e = ux * ry - uy * rx
        s = (xp.astype(k, xp.float64) + t) * DS
        return k, s, e, ux, uy

    def step(self, obs: dict, dt: float):
        xp, n = self.xp, self.n
        valid = xp.asarray(obs["valid"], xp.bool)
        k, s, e, ux, uy = self._place(obs["x"], obs["y"], self.k_self, self.placed,
                                      self._all_placed)
        self.k_self = xp.where(valid, k, self.k_self)
        self.placed = self.placed | valid
        if not self._all_placed:    # a sync, only until every slot is placed
            self._all_placed = not xp.any(~self.placed)
        v = xp.maximum(obs["vx"] * ux + obs["vy"] * uy, xp.zeros(n))
        lost = valid & (xp.abs(e) > LOST_OFFSET) & ~self.lost

        lvalid = valid & xp.asarray(obs["leader_valid"], xp.bool)
        kl, sl, el, lux, luy = self._place(obs["leader_x"], obs["leader_y"], self.k_lead,
                                           self.lead_placed, self._all_lead_placed)
        self.k_lead = xp.where(lvalid, kl, self.k_lead)
        self.lead_placed = self.lead_placed | lvalid
        if not self._all_lead_placed:
            self._all_lead_placed = not xp.any(~self.lead_placed)
        vl = obs["leader_vx"] * lux + obs["leader_vy"] * luy
        leads = lvalid & (sl > s) & (xp.abs(el) <= self.half_width)

        # the gap: to the leader's rear, or to the lane's end (a standing obstacle)
        # positions are entity origins (SSv2's: a vehicle's rear axle); the gap is box to box
        gap_lead = (sl + self.lead_rear) - (s + self.front)
        gap_end = self.end_s - (s + self.front)
        use_lead = leads & (gap_lead < gap_end)
        gap = xp.where(use_lead, gap_lead, gap_end)
        dv = xp.where(use_lead, v - vl, v)
        gap = xp.maximum(gap, xp.full(n, MIN_GAP))

        r = v / self.v0
        r2 = r * r
        s_star = self.s0 + v * self.T + v * dv / self.two_sqrt_ab
        q = s_star / gap
        a_idm = self.a * (1.0 - r2 * r2 - q * q)
        capped = valid & (a_idm < -self.max_decel)
        a_cmd = xp.minimum(xp.maximum(a_idm, -self.max_decel), self.max_accel)

        speed = xp.maximum(v + a_cmd * dt, xp.zeros(n))
        accel_limit = xp.maximum(xp.abs(a_cmd), xp.full(n, MIN_ACCEL))
        corr = xp.minimum(xp.maximum(-e / xp.full(n, LOOKAHEAD), xp.full(n, -MAX_CORRECTION)),
                          xp.full(n, MAX_CORRECTION))
        heading = self._seg(self.H, k) + corr

        stopped = valid & (speed < STOP_SPEED)
        ev = xp.zeros(n, xp.int64)
        ev = xp.where(valid & use_lead & ~self.following, xp.full(n, FOLLOW, xp.int64), ev)
        ev = xp.where(valid & ~use_lead & self.following, xp.full(n, FREE, xp.int64), ev)
        ev = xp.where(stopped & ~self.stopped, xp.full(n, STOPPED, xp.int64), ev)
        ev = xp.where(capped, xp.full(n, CAPPED, xp.int64), ev)
        ev = xp.where(lost, xp.full(n, LOST, xp.int64), ev)
        self.following = xp.where(valid, use_lead, self.following)
        self.stopped = xp.where(valid, stopped, self.stopped)
        self.lost = self.lost | lost
        return {"speed": speed, "heading": heading, "accel_limit": accel_limit}, ev

    def record(self) -> list:
        """Per slot, what a run's record keeps: the model, its parameters as resolved (v0 and
        the set's s0, T, a, b filled in) and its set (name, sha256, source)."""
        out = []
        for p, h in zip(self.params, self._host):
            st = self.sets[p["parameter_set"]]
            out.append({
                "model": f"scensim.behaviour:{self.name}",
                "params": dict(p, v0=h["v0"], s0=h["s0"], T=h["T"], a=h["a"], b=h["b"]),
                "parameter_set": {"name": st["name"], "sha256": st["sha256"],
                                  "source": st["source"]["id"]},
                "seed": None,
            })
        return out
