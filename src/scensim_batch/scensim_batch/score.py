"""The batch's score in the batch (roadmap 092 K11f): each slot's closest approach of the ego to
any other entity, box to box, kept while the batch runs, so a search's generation needs no truth
export to be scored.

    cg = ClosestGap(run)
    cg.begin(run.reset())
    for ...: cg.record(run.step(...))
    rows = cg.rows()          # scensim.truth.slot_outcomes' rows, without the files

The gap is the one `scensim.truth.closest` measures on the export (gap_geometry's
`signed_distance` between the declared boxes at the batch's poses, the batch's origin offset
0): the clearance where the boxes are apart, minus the penetration depth where they overlap, 0
within the touch tolerance. Each slot's episode keeps its smallest gap with closest()'s
tie-break: the first strict minimum, frames in order, then entities in their order. `contact`
is the storyboard's overlap, at any frame of the episode, as the export's contact lines are.
Episodes open, close and are numbered as TruthRecorder's are (issue 199).
"""
import torch

from . import storyboard as sbmod

# gap_geometry.TOUCH_TOLERANCE: below it a margin is "touching"
TOUCH_TOLERANCE = 1e-9


def _corners(b):
    """[..., 4, 2], counter-clockwise from front-left, as gap_geometry.OrientedBox.corners."""
    cx, cy, yaw, hl, hw = b.unbind(-1)
    ux, uy = torch.cos(yaw), torch.sin(yaw)
    vx, vy = -uy, ux
    out = [torch.stack([cx + sl * hl * ux + sw * hw * vx, cy + sl * hl * uy + sw * hw * vy], -1)
           for sl, sw in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    return torch.stack(out, -2), ((ux, uy), (vx, vy))


def _project(c, ax, ay):
    p = c[..., 0] * ax[..., None] + c[..., 1] * ay[..., None]
    return p.min(-1).values, p.max(-1).values


def _point_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    safe = torch.where(length2 == 0, torch.ones_like(length2), length2)
    t = (((px - ax) * dx + (py - ay) * dy) / safe).clamp(0.0, 1.0)
    t = torch.where(length2 == 0, torch.zeros_like(t), t)
    return torch.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _polygon_distance(ca, cb):
    """Distance between disjoint convex polygons: every vertex of each to every edge of the
    other."""
    best = None
    for poly, other in ((ca, cb), (cb, ca)):
        a = other
        b = torch.roll(other, -1, dims=-2)
        p = poly[..., :, None, :]                       # [..., 4, 1, 2]
        d = _point_segment(p[..., 0], p[..., 1], a[..., None, :, 0], a[..., None, :, 1],
                           b[..., None, :, 0], b[..., None, :, 1])
        m = d.flatten(-2).min(-1).values
        best = m if best is None else torch.minimum(best, m)
    return best


def signed_distance(a, b):
    """gap_geometry.signed_distance over tensors: `a`, `b` boxes [..., 5] as (centre x, centre y,
    yaw, half length, half width), broadcast together. Clearance (> 0), or minus the
    penetration depth (< 0), 0 touching."""
    a, b = torch.broadcast_tensors(a, b)
    ca, axes_a = _corners(a)
    cb, axes_b = _corners(b)
    sep = torch.zeros(a.shape[:-1], dtype=torch.bool, device=a.device)
    depth = torch.full(a.shape[:-1], float("inf"), dtype=a.dtype, device=a.device)
    for ax, ay in (*axes_a, *axes_b):
        mina, maxa = _project(ca, ax, ay)
        minb, maxb = _project(cb, ax, ay)
        sep = sep | (maxa < minb) | (maxb < mina)
        depth = torch.minimum(depth, torch.minimum(maxa - minb, maxb - mina))
    inside = torch.where(depth > TOUCH_TOLERANCE, -depth, torch.zeros_like(depth))
    return torch.where(sep, _polygon_distance(ca, cb), inside)


class _Frame:
    """storyboard.overlap's context over one observation."""

    def __init__(self, run, obs):
        self.run, self.n, self.obs = run, run.c.n, obs

    def col(self, name, i):
        return self.obs[name][:, i]


class ClosestGap:
    """Each slot's closest gap of the ego to any other entity, per episode, as the batch runs
    (092 K11f). `begin` and `record` take the observations TruthRecorder takes, at the same
    calls; the step's time is the run's clock (`run.ctx.t`)."""

    def __init__(self, run):
        self.run = run
        c = run.c
        self.n, self.ego = c.n, run.ego
        self.names = [e.name for e in c.entities]
        self.others = [i for i in range(len(c.entities)) if i != self.ego]
        self._dims = [(e.cx, e.cy, e.length / 2.0, e.width / 2.0) for e in c.entities]
        n = self.n
        self.open = torch.zeros(n, dtype=torch.bool)
        self.started = [False] * n      # whether the slot has had an episode (issue 199)
        self.episode = [0] * n
        self.frame = torch.zeros(n, dtype=torch.int64)
        self.done = []          # (slot, episode, gap, entity, frame, sim_time, contact)
        self._reset(torch.ones(n, dtype=torch.bool))

    def _reset(self, mask):
        n = self.n
        if not hasattr(self, "best"):
            self.best = torch.full((n,), float("inf"), dtype=torch.float64)
            self.best_entity = torch.full((n,), -1, dtype=torch.int64)
            self.best_frame = torch.zeros(n, dtype=torch.int64)
            self.best_time = torch.zeros(n, dtype=torch.float64)
            self.contact = torch.zeros(n, dtype=torch.bool)
        self.best = torch.where(mask, torch.full_like(self.best, float("inf")), self.best)
        self.best_entity = torch.where(mask, torch.full_like(self.best_entity, -1),
                                       self.best_entity)
        self.contact = self.contact & ~mask
        self.frame = torch.where(mask, torch.zeros_like(self.frame), self.frame)

    def _box(self, obs, i):
        cx, cy, hl, hw = self._dims[i]
        x, y, h = obs["x"][:, i], obs["y"][:, i], obs["yaw"][:, i]
        c, s = torch.cos(h), torch.sin(h)
        # gap_geometry.box_at: the declared centre rotated into the pose's frame
        return torch.stack([x + (c * cx - s * cy), y + (s * cx + c * cy), h,
                            torch.full_like(x, hl), torch.full_like(x, hw)], -1)

    def _update(self, obs):
        t = torch.as_tensor(self.run.ctx.t, dtype=torch.float64).detach().cpu()
        ego = self._box(obs, self.ego)
        ctx = _Frame(self.run, obs)
        for i in self.others:
            d = signed_distance(ego, self._box(obs, i)).detach().cpu().to(torch.float64)
            up = self.open & (d < self.best)
            self.best = torch.where(up, d, self.best)
            self.best_entity = torch.where(up, torch.full_like(self.best_entity, i),
                                           self.best_entity)
            self.best_frame = torch.where(up, self.frame, self.best_frame)
            self.best_time = torch.where(up, t, self.best_time)
            hit = sbmod.overlap(ctx, self.ego, i).detach().cpu()
            self.contact = self.contact | (self.open & hit)

    def _close(self, k):
        self.done.append((k, self.episode[k], float(self.best[k]), int(self.best_entity[k]),
                          int(self.best_frame[k]), float(self.best_time[k]),
                          bool(self.contact[k])))
        self.open[k] = False

    def begin(self, obs, mask=None):
        """Start an episode for the slots in `mask` (all) at the reset's observation."""
        n = self.n
        mask = (torch.ones(n, dtype=torch.bool) if mask is None
                else torch.as_tensor(mask, dtype=torch.bool).cpu())
        for k in torch.nonzero(mask).flatten().tolist():
            if bool(self.open[k]):
                self._close(k)
            if self.started[k]:     # a new number, as TruthRecorder's (issue 199)
                self.episode[k] += 1
            self.started[k] = True
        self.frame = torch.where(self.open & ~mask, self.frame + 1, self.frame)
        self._reset(mask)
        self.open = self.open | mask
        self._update(obs)

    def record(self, obs):
        """One step's observation; a slot whose outcome is no longer running closes its
        episode, this frame its last."""
        self.frame = torch.where(self.open, self.frame + 1, self.frame)
        self._update(obs)
        out = obs.get("outcome")
        if out is not None:
            ended = self.open & (torch.as_tensor(out).detach().cpu() != 0)
            for k in torch.nonzero(ended).flatten().tolist():
                self._close(k)

    def episodes(self):
        """Every closed episode and every open one, by (slot, episode)."""
        eps = list(self.done) + [
            (k, self.episode[k], float(self.best[k]), int(self.best_entity[k]),
             int(self.best_frame[k]), float(self.best_time[k]), bool(self.contact[k]))
            for k in range(self.n) if bool(self.open[k])]
        return sorted(eps, key=lambda e: (e[0], e[1]))

    def rows(self, threshold=0.0):
        """scensim.truth.slot_outcomes' rows: `[{record, outcome}]`, a run failing at a gap at
        most `threshold`."""
        recs = self.run.c.records
        rows = []
        for k, e, gap, ent, frame, t, contact in self.episodes():
            rec = recs[k] if k < len(recs) else {}
            rid = rec.get("id") if isinstance(rec, dict) else None
            name = f"slot_{k}_ep{e}"
            if not rid:
                raise ValueError(f"{name}: the slot's record has no record id")
            if ent < 0:
                rows.append({"record": rid, "outcome": {
                    "error": True, "message": "no ego and other entity to measure",
                    "run": name}})
                continue
            rows.append({"record": rid, "outcome": {
                "score": gap, "failed": gap <= threshold, "contact": contact, "error": False,
                "closest": {"entity": self.names[ent], "frame": frame, "sim_time": t},
                "run": name}})
        return rows
