"""The batch's world adapter on a Lanelet2 map (roadmap 092 K2.6): the map queries
scensim_batch makes (compile, npc, storyboard), answered as SSv2's traffic simulator answers
them, from the map's export (map_export.py), with no lanelet2 at run time:

    world = LaneletWorld.load("town01_map.json", map_dir=<the map in use>)   # digest checked
    world = LaneletWorld.from_polylines({1: [[x, y], ...]}, following={1: [1]})   # a track

The geometry is SSv2's, ported: a lanelet's centreline is a Catmull-Rom spline of Hermite
curves through its centre points (math::geometry::CatmullRomSpline, HermiteCurve), each
curve's length its 100-step sum, s mapped to the curve's parameter linearly (s / length, as
SSv2 does); the tangent is the raw derivative in that parameter, not a unit vector; a point's
lanelet pose is SSv2's toLaneletPose (the lanelets within 0.1 m of the point, the nearest five,
crosswalks excluded, in order of distance; the first whose spline the pose's ±1 m normal
crosses, within 45 degrees of its heading either way); a route is SSv2's followingLanelets
(straight first, else the first follower), its points on one spline through the lanelets'
centre points joined (SSv2's centerPoints(ids), consecutive duplicates removed).

The interface (what the stand-in worlds of the tests offer, so a polyline world, P2's oval
track, is the same object):

- `lane_pose(lanes, s, offset)` -> (x, y, yaw) [N]
- `route(x, y, yaw, length, points)` -> [..., points, 2], from each pose along its lanes
- `speed_limit(x, y)` -> [...] m/s
- `lanelet_pose(x, y, yaw)` -> (lane, s, offset) | None
- `along_lanelet(lane, s, distance)` -> (lane, s)
- `can_change_lane(frm, to)`, `adjacent_lane(lane, direction, shift)`
- `collision_s(lane, p0, p1)` -> s | None, `tangent(lane, s)` -> (tx, ty)

Differences from SSv2, named: the lanelet pose ignores the entity's bounding box (SSv2's
matchToLane runs first for an entity with one) and its altitude check (the batch is 2D).
"""
import json
import math
from pathlib import Path

import torch

from . import map_export

TOL = 1e-7                  # SSv2's PolynomialSolver::tolerance
EPS = 2.220446049250313e-16
MATCHING_DISTANCE = 1.0     # SSv2's default for toLaneletPose
NEARBY_DISTANCE = 0.1       # nearbyLaneletIds' distance_threshold and search_count
NEARBY_COUNT = 5
YAW_THRESHOLD = math.radians(45.0)


# --- SSv2's polynomial solver ------------------------------------------------------------------

def _approx(a, b):
    return abs(a - b) <= TOL


def _filter(values, lo, hi):
    out = []
    for v in values:
        if lo <= v <= hi:
            out.append(v)
        elif abs(v - hi) <= TOL:
            out.append(hi)
        elif abs(v - lo) <= TOL:
            out.append(lo)
    return out


def _linear(a, b, lo, hi):
    if _approx(a, 0):
        if _approx(b, 0):
            raise ValueError("a linear equation 0 x + 0 = 0")
        return []
    return _filter([-b / a], lo, hi)


def _quadratic(a, b, c, lo, hi):
    if _approx(a, 0):
        return _linear(b, c, lo, hi)
    disc = b * b - 4 * a * c
    if _approx(disc, 0):
        sols = [-b / (2 * a)]
    elif disc < 0:
        sols = []
    else:
        r = math.sqrt(disc)
        sols = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    return _filter(sols, lo, hi)


def _monic_cubic(a, b, c):
    """Real roots of x^3 + a x^2 + b x + c (SSv2's solveMonicCubicEquationWithComplex, then
    its real parts with |imag| <= eps)."""
    q = (a * a - 3 * b) / 9
    r = (a * (2 * a * a - 9 * b) + 27 * c) / 54
    q3 = q * q * q
    if r * r <= q3 + TOL:
        if q3 <= 0:      # sqrt of a negative, or 0/0: NaN roots in SSv2, which none passes
            return []
        t = math.acos(max(-1.0, min(1.0, r / math.sqrt(q3))))
        sq = math.sqrt(q)
        return [-2 * sq * math.cos(t / 3) - a / 3,
                -2 * sq * math.cos((t + 2 * math.pi) / 3) - a / 3,
                -2 * sq * math.cos((t - 2 * math.pi) / 3) - a / 3]
    real = -((abs(r) + math.sqrt(r * r - q3)) ** (1.0 / 3.0))
    A = -real if r < 0 else real
    B = 0.0 if _approx(A, 0) else q / A
    imag = 0.5 * math.sqrt(3.0) * (A - B)
    if _approx(imag, 0):
        return [(A + B) - a / 3, -0.5 * (A + B) - a / 3]
    return [(A + B) - a / 3]     # the other two have an imaginary part above eps


def _cubic(a, b, c, d, lo, hi):
    if _approx(a, 0):
        return _quadratic(b, c, d, lo, hi)
    return _filter(_monic_cubic(b / a, c / a, d / a), lo, hi)


# --- SSv2's Hermite curve and Catmull-Rom spline -----------------------------------------------

class Hermite:
    """x(t) = ax t^3 + bx t^2 + cx t + dx (and y, z), t in [0, 1]."""

    __slots__ = ("c", "length")

    def __init__(self, cx, cy, cz):
        self.c = (cx, cy, cz)
        self.length = self._length(100)

    def _length(self, n):
        (ax, bx, cx, _), (ay, by, cy, _), (az, bz, cz, _) = self.c
        ret, ds = 0.0, 1.0 / n
        for i in range(n):
            s = i * ds
            x = 3 * s * s * ax + 2 * s * bx + cx
            y = 3 * s * s * ay + 2 * s * by + cy
            z = 3 * s * s * az + 2 * s * bz + cz
            ret += math.sqrt(x * x + y * y + z * z) * ds
        return ret

    def point(self, t):
        return tuple(a * t ** 3 + b * t * t + c * t + d for a, b, c, d in self.c)

    def tangent(self, t):
        return tuple(3 * a * t * t + 2 * b * t + c for a, b, c, _ in self.c)

    def collisions(self, p0, p1):
        """SSv2's getCollisionPointsIn2D(point0, point1): the curve's parameters where it
        crosses the segment p0-p1."""
        (ax, bx, cx, dx), (ay, by, cy, dy), _ = self.c
        fx, ex = p0[0], p1[0] - p0[0]
        fy, ey = p0[1], p1[1] - p0[1]
        a = ay * ex - ax * ey
        b = by * ex - bx * ey
        c = cy * ex - cx * ey
        d = dy * ex - dx * ey - ex * fy + ey * fx
        if _approx(a, 0) and _approx(b, 0) and _approx(c, 0) and _approx(d, 0):
            sols = [0.0]
        else:
            sols = _cubic(a, b, c, d, 0.0, 1.0)
        out = set()
        for t in sols:
            x = ax * t ** 3 + bx * t * t + cx * t + dx
            y = ay * t ** 3 + by * t * t + cy * t + dy
            with_nan = lambda num, den: num / den if den != 0 else (  # noqa: E731
                math.copysign(math.inf, num) if num != 0 else math.nan)
            tx, ty = with_nan(x - p0[0], ex), with_nan(y - p0[1], ey)
            if abs(tx - ty) > EPS or math.isnan(tx) or math.isnan(ty):
                if 0 <= tx <= 1 or 0 <= ty <= 1:
                    out.add(t)
            elif 0 <= tx <= 1 and 0 <= ty <= 1:
                out.add(t)
        return out


def _catmull_curves(p):
    """SSv2's CatmullRomSpline curves through control points `p` (three or more)."""
    n = len(p) - 1
    curves = []
    for i in range(n):
        axes = []
        for k in range(3):
            if i == 0:
                a, b = 0.0, p[0][k] - 2 * p[1][k] + p[2][k]
                c, d = -3 * p[0][k] + 4 * p[1][k] - p[2][k], 2 * p[0][k]
            elif i == n - 1:
                a, b = 0.0, p[i - 1][k] - 2 * p[i][k] + p[i + 1][k]
                c, d = -p[i - 1][k] + p[i + 1][k], 2 * p[i][k]
            else:
                a = -p[i - 1][k] + 3 * p[i][k] - 3 * p[i + 1][k] + p[i + 2][k]
                b = 2 * p[i - 1][k] - 5 * p[i][k] + 4 * p[i + 1][k] - p[i + 2][k]
                c, d = -p[i - 1][k] + p[i + 1][k], 2 * p[i][k]
            axes.append((a * 0.5, b * 0.5, c * 0.5, d * 0.5))
        curves.append(Hermite(*axes))
    return curves


class Spline:
    """SSv2's CatmullRomSpline (three or more control points)."""

    def __init__(self, points):
        pts = [tuple(float(v) for v in (list(q) + [0.0] * (3 - len(q)))[:3]) for q in points]
        if len(pts) < 3:
            raise ValueError(f"a spline needs three points, got {len(pts)}")
        self.points = pts
        self.curves = _catmull_curves(pts)
        self.lengths = [c.length for c in self.curves]
        self.length = sum(self.lengths)

    def index_and_s(self, s):
        if s < 0:
            return 0, s
        if s >= self.length:
            return len(self.curves) - 1, s - (self.length - self.lengths[-1])
        acc = 0.0
        for i, ln in enumerate(self.lengths):
            if acc <= s < acc + ln:
                return i, s - acc
            acc += ln
        return len(self.curves) - 1, s - (self.length - self.lengths[-1])

    def _t(self, s):
        i, local = self.index_and_s(s)
        return self.curves[i], local / self.curves[i].length

    def point(self, s, offset=0.0):
        c, t = self._t(s)
        x, y, z = c.point(t)
        if offset:
            tx, ty, _ = c.tangent(t)
            th = math.atan2(tx, -ty)     # the normal: the tangent turned by +90 degrees
            x, y = x + offset * math.cos(th), y + offset * math.sin(th)
        return x, y, z

    def tangent(self, s):
        c, t = self._t(s)
        return c.tangent(t)

    def yaw(self, s):
        tx, ty, _ = self.tangent(s)
        return math.atan2(ty, tx)

    def s_value(self, x, y, yaw, threshold, quat=None):
        """SSv2's getSValue(pose, threshold): where the pose's y axis (±threshold) first
        crosses the spline. The pose is (x, y, yaw), or its full orientation `quat` (x, y, z,
        w), as SSv2 transforms the segment's ends."""
        if quat is None:
            ey = (-math.sin(yaw), math.cos(yaw))
        else:
            qx, qy, qz, qw = quat
            ey = (2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz))   # R's second column
        p0 = (x + threshold * ey[0], y + threshold * ey[1])
        p1 = (x - threshold * ey[0], y - threshold * ey[1])
        acc = 0.0
        for c in self.curves:
            ts = c.collisions(p0, p1)
            if ts:
                return acc + min(ts) * c.length
            acc += c.length
        return None

    def collision_s(self, polygon, search_backward=False):
        """SSv2's getCollisionPointIn2D(polygon): the first s (the last, `search_backward`)
        where the closed polygon's edges cross the spline (two points: the segment both
        ways)."""
        poly = [tuple(p[:2]) for p in polygon]
        if len(poly) < 2:
            raise ValueError("a polygon of fewer than two points")
        edges = list(zip(poly, poly[1:])) + [(poly[-1], poly[0])]
        out = set()
        acc = 0.0
        for c in self.curves:
            for a, b in edges:
                out |= {acc + t * c.length for t in c.collisions(a, b)}
            acc += c.length
        if not out:
            return None
        return max(out) if search_backward else min(out)


# --- geometry helpers --------------------------------------------------------------------------

def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 <= 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _inside(px, py, poly):
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def _poly_dist(px, py, poly):
    """lanelet2's 2D distance from a point to a lanelet's polygon (0 inside)."""
    if _inside(px, py, poly):
        return 0.0
    return min(_seg_dist(px, py, *a, *b) for a, b in zip(poly, poly[1:] + poly[:1]))


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


# --- the world ---------------------------------------------------------------------------------

class LaneletWorld:
    def __init__(self, lanelets, name="", sha256=None):
        self.lanelets = {int(k): v for k, v in lanelets.items()}
        self.name, self.sha256 = name, sha256
        self._splines = {}
        self._polys = {}
        self._boxes = []     # (xmin, ymin, xmax, ymax, id): the nearby search's prefilter
        for k, v in self.lanelets.items():
            if "left_bound" in v and "right_bound" in v:
                poly = ([tuple(p[:2]) for p in v["left_bound"]]
                        + [tuple(p[:2]) for p in reversed(v["right_bound"])])
                self._polys[k] = poly
                xs, ys = [p[0] for p in poly], [p[1] for p in poly]
                self._boxes.append((min(xs), min(ys), max(xs), max(ys), k))

    @classmethod
    def load(cls, path, map_dir=None, map_sha256=None):
        """The export at `path`, refused unless its digest is the map's in use (`map_dir`, or
        the digest `map_sha256`) when either is given, and refused for another format."""
        doc = json.loads(Path(path).read_text())
        if doc.get("format") != map_export.FORMAT or doc.get("version") != map_export.VERSION:
            raise ValueError(f"{path}: not a {map_export.FORMAT} v{map_export.VERSION} export")
        want = map_sha256 or (map_export.map_digest(map_dir) if map_dir is not None else None)
        if want is not None and doc["map_sha256"] != want:
            raise ValueError(f"{path}: exported from map {doc['map']} {doc['map_sha256'][:12]}, "
                             f"not the map in use ({want[:12]}): export it again "
                             "(python3 -m scensim_batch.map_export)")
        return cls(doc["lanelets"], doc["map"], doc["map_sha256"])

    @classmethod
    def from_polylines(cls, centerlines, following=None, speed_limit=30.0, width=None):
        """A world of polylines only (a track): `centerlines` {id: [[x, y], ...]}, `following`
        {id: [ids]} (a closed loop follows itself), every lanelet a road at `speed_limit`;
        `width` (m) gives each its bounds, for lanelet_pose's nearby search."""
        lanelets = {}
        for k, pts in centerlines.items():
            pts = [list(p)[:2] + [0.0] for p in pts]
            if len(pts) == 2:
                pts.insert(1, [(pts[0][i] + pts[1][i]) / 2 for i in range(3)])
            v = {"centerline": pts, "subtype": "road", "turn_direction": "else",
                 "following": list((following or {}).get(k, [])), "previous": [],
                 "left": None, "right": None, "adjacent_left": None, "adjacent_right": None,
                 "speed_limit": float(speed_limit), "speed_limit_tagged": True}
            if width is not None:
                sp = Spline(pts)
                n = max(2, int(sp.length / 0.5) + 1)
                ss = [sp.length * i / (n - 1) for i in range(n)]
                v["left_bound"] = [list(sp.point(s, width / 2)[:2]) for s in ss]
                v["right_bound"] = [list(sp.point(s, -width / 2)[:2]) for s in ss]
            lanelets[k] = v
        for k, v in lanelets.items():
            for f in v["following"]:
                lanelets[f]["previous"].append(k)
        return cls(lanelets, "polylines")

    # --- splines --------------------------------------------------------------------------

    def spline(self, lane):
        lane = int(lane)
        sp = self._splines.get(lane)
        if sp is None:
            sp = self._splines[lane] = Spline(self.lanelets[lane]["centerline"])
        return sp

    def length(self, lane):
        return self.spline(lane).length

    def following(self, lane, distance, include_self=True):
        """SSv2's followingLanelets(lane, distance): the straight follower first, else the
        first."""
        out = [int(lane)] if include_self else []
        total, ref = 0.0, int(lane)
        while total < distance:
            nxt = self.lanelets[ref]["following"]
            straight = [f for f in nxt if self.lanelets[f]["turn_direction"] == "straight"]
            pick = straight[0] if straight else (nxt[0] if nxt else None)
            if pick is None:
                break
            total += self.length(pick)
            out.append(pick)
            ref = pick
        return out

    # --- the interface ----------------------------------------------------------------------

    def lane_pose(self, lanes, s, offset):
        s = torch.as_tensor(s, dtype=torch.float64).reshape(-1)
        offset = torch.as_tensor(offset, dtype=torch.float64).reshape(-1)
        lanes = [int(v) for v in (lanes.tolist() if torch.is_tensor(lanes) else lanes)]
        out = [self._pose(ln, float(si), float(oi)) for ln, si, oi in zip(lanes, s, offset)]
        x, y, h = zip(*out) if out else ((), (), ())
        t = lambda v: torch.tensor(v, dtype=torch.float64)   # noqa: E731
        return t(x), t(y), t(h)

    def _pose(self, lane, s, offset):
        sp = self.spline(lane)
        x, y, _ = sp.point(s, offset)
        return x, y, sp.yaw(s)

    def nearby(self, x, y, include_crosswalk=False):
        """SSv2's nearbyLaneletIds(point, 0.1, include_crosswalk, 5)."""
        # only a lanelet whose box is within the threshold can be (lanelet2's findNearest of
        # the five nearest, then those within it: the same set once no others are near)
        cand = [k for x0, y0, x1, y1, k in self._boxes
                if x0 - NEARBY_DISTANCE <= x <= x1 + NEARBY_DISTANCE
                and y0 - NEARBY_DISTANCE <= y <= y1 + NEARBY_DISTANCE]
        d = sorted((_poly_dist(x, y, self._polys[k]), k) for k in cand)[:NEARBY_COUNT]
        if not include_crosswalk:   # SSv2 keeps only lanelets with a subtype, not crosswalks
            d = [(dist, k) for dist, k in d
                 if self.lanelets[k].get("subtype") not in (None, "crosswalk")]
        return [k for dist, k in d if dist <= NEARBY_DISTANCE]

    def lanelet_pose(self, x, y, yaw, matching_distance=MATCHING_DISTANCE, lanes=None):
        """(lane, s, offset) of a pose, or None (SSv2's toLaneletPose)."""
        x, y, yaw = float(x), float(y), float(yaw)
        for lane in (self.nearby(x, y) if lanes is None else lanes):
            sp = self.spline(lane)
            s = sp.s_value(x, y, yaw, matching_distance)
            if s is None:
                continue
            rel = _wrap(yaw - sp.yaw(s))
            if YAW_THRESHOLD < abs(rel) < math.pi - YAW_THRESHOLD:
                continue
            px, py, _ = sp.point(s)
            tx, ty, _ = sp.tangent(s)
            off = math.hypot(x - px, y - py)
            if (-ty) * (x - px) + tx * (y - py) < 0:   # the normal's side
                off = -off
            return lane, s, off
        return None

    def route(self, x, y, yaw, length, points):
        x = torch.as_tensor(x, dtype=torch.float64)
        y = torch.as_tensor(y, dtype=torch.float64)
        yaw = torch.as_tensor(yaw, dtype=torch.float64)
        shape = x.shape
        out = []
        for xi, yi, hi in zip(x.reshape(-1).tolist(), y.reshape(-1).tolist(),
                              yaw.reshape(-1).tolist()):
            out.append(self._route(xi, yi, hi, float(length), int(points)))
        return torch.tensor(out, dtype=torch.float64).reshape(*shape, int(points), 2)

    def _route(self, x, y, yaw, length, points):
        lp = self.lanelet_pose(x, y, yaw)
        if lp is None:
            raise ValueError(f"({x:.2f}, {y:.2f}, yaw {yaw:.3f}) is on no lanelet: no route")
        lane, s0, _ = lp
        ids = self.following(lane, s0 + length)
        pts = []
        for k in ids:
            for q in self.lanelets[k]["centerline"]:
                q = tuple(q)
                if not pts or pts[-1] != q:
                    pts.append(q)
        sp = Spline(pts)
        # where the pose is on the joined spline, as SSv2 projects an entity onto its route's
        # (the joined spline is not the lanelet's near the joints)
        sj = sp.s_value(x, y, yaw, MATCHING_DISTANCE)
        s0 = s0 if sj is None else sj
        return [list(sp.point(s0 + length * i / max(points - 1, 1))[:2]) for i in range(points)]

    def speed_limit(self, x, y):
        x = torch.as_tensor(x, dtype=torch.float64)
        y = torch.as_tensor(y, dtype=torch.float64)
        out = []
        for xi, yi in zip(x.reshape(-1).tolist(), y.reshape(-1).tolist()):
            near = self.nearby(xi, yi)
            out.append(self.lanelets[near[0]]["speed_limit"] if near else math.nan)
        return torch.tensor(out, dtype=torch.float64).reshape(x.shape)

    def along_lanelet(self, lane, s, distance):
        """The lanelet and s `distance` on along the following lanelets (SSv2's
        moveAlongLaneletPose on followingLanelets)."""
        lane, s = int(lane), float(s) + float(distance)
        while s > self.length(lane):
            nxt = self.following(lane, 1e-9, include_self=False)
            if not nxt:
                break
            s -= self.length(lane)
            lane = nxt[0]
        return lane, s

    def can_change_lane(self, frm, to):
        v = self.lanelets[int(frm)]
        return int(to) in (v["left"], v["right"])

    def adjacent_lane(self, lane, direction, shift):
        """The lane `shift` lane changes `direction` ("left" | "right") away, or None."""
        lane = int(lane)
        for _ in range(int(shift)):
            lane = self.lanelets[lane][direction]
            if lane is None:
                return None
        return lane

    def collision_s(self, lane, p0, p1):
        return self.spline(lane).collision_s([p0, p1])

    def tangent(self, lane, s):
        tx, ty, _ = self.spline(lane).tangent(float(s))
        return tx, ty
