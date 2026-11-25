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

from .catmull import (  # noqa: F401 - the spline geometry, torch-free (issue 166)
    TOL, EPS, MATCHING_DISTANCE, NEARBY_DISTANCE, NEARBY_COUNT, YAW_THRESHOLD, _approx, _filter,
    _linear, _quadratic, _monic_cubic, _cubic, Hermite, _catmull_curves, Spline, _seg_dist,
    _inside, _poly_dist, _wrap)


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
