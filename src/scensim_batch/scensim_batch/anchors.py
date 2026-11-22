"""A map's anchors resolved to numbers (roadmap 092 K9a; scenario-description.md section 3).

A map's author declares its anchors in `anchors.yaml`, beside `lanelet2_map.osm`, and runs,
once, where scensim_batch runs (it needs torch, for world_lanelet):

    python3 -m scensim_batch.anchors resolve <map dir> --export <the map's export.json>

which writes `<map dir>/anchors.resolved.json`. Users never run it: the sampler and
`testbench check` read the resolved file with ROS 2 alone (scensim_sampler.anchors), refusing it
when its `map_sha256` is not the map's in use.

`anchors.yaml` (version 1; K9a resolves lanes, K9c adds conflicts, curves and regions):

    anchors: 1
    lanes:
      exit_n: {lanelets: [1234, 1240]}   # a route of lanelets, each following the one before;
                                         # s runs from the first's start

A conflict names two of the file's lanes that cross once (`conflicts: {<name>: {lanes: [<lane>,
<other lane>]}}`) and resolves to where: `s_<lane>` for each (lane position, m), `x`, `y`, the
`angle` between them there, and `position_error` (m, the two centrelines' points apart).

A curve is a stretch of a lane (`curves: {<name>: {lane, from_s, to_s}}`): its `length`,
`turn` (rad, positive left), `direction`, `min_radius` (over 2 m) and `mean_radius`. A region
is a polygon in the map frame (`regions: {<name>: {polygon: [[x, y], ...]}}`): its `area`,
centroid `x`, `y`, and for each of the file's lanes that enters it once, `from_<lane>` and
`to_<lane>`.

A lane resolves to its `length` (m: the sum of its lanelets' SSv2 splines, world_lanelet's
Catmull-Rom, so an s here is an s in a LanePosition), `speed_limit` (m/s, the lowest of its
lanelets'), `start_x`, `start_y`, `end_x`, `end_y`, its lanelets with their s ranges, and
`heading` (rad, the map frame) and the centreline's `x` and `y` at `heading_s`: every `HEADING_STEP` m within each lanelet, and
each lanelet's start and end, so a join between two lanelets is listed twice (the end of the
one before, then the start of the one after: their splines meet at an angle, and no interval
straddles it), and likewise each boundary between the curves of a lanelet's spline (SSv2's
Catmull-Rom is a chain of curves whose tangents need not meet); an interval whose linear
interpolation is off by more than `HEADING_TOLERANCE` is halved, down to `HEADING_MIN_STEP`.
`heading_max_error` is the largest difference between that table, interpolated linearly, and
the spline's heading at four points inside each interval: at most the tolerance unless the
minimum step stopped a halving.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import yaml

from . import map_export

FORMAT = "scensim-anchors"
VERSION = 1
DECLARATION = "anchors.yaml"
RESOLVED = "anchors.resolved.json"
HEADING_STEP = 0.5
HEADING_TOLERANCE = 1e-3   # rad: an interval off by more is halved
HEADING_MIN_STEP = 0.01    # m: but not below
KINDS_LATER = ("points",)   # stated in testbench.yaml's world.anchors, not resolved
CURVE_STEP = 0.1           # m: a curve's heading sampled this finely
CURVE_WINDOW = 2.0         # m: its radius from the heading's change over this much lane (a
                           # centreline of points 0.25 m apart wiggles: shorter chords read noise)
REGION_STEP = 0.1          # m: a lane sampled this finely against a region
CONFLICT_STEP = 0.25       # m: each lane sampled this finely to find where they cross
CONFLICT_FINE = 0.002      # m: then again around each crossing


class AnchorError(ValueError):
    pass


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _declaration(path):
    doc = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(doc, dict) or doc.get("anchors") != 1:
        raise AnchorError(f"{path}: not an anchors file (anchors: 1)")
    unknown = sorted(set(doc) - {"anchors", "lanes", "conflicts", "curves", "regions"}
                     - set(KINDS_LATER))
    if unknown:
        raise AnchorError(f"{path}: unknown section(s) {', '.join(unknown)} (lanes; "
                          f"{', '.join(KINDS_LATER)} come with 092 K9c)")
    later = [k for k in KINDS_LATER if doc.get(k)]
    if later:
        raise AnchorError(f"{path}: {', '.join(later)}: a map's file resolves lanes, conflicts, "
                          f"curves and regions; a point is stated (testbench.yaml world.anchors)")
    return {k: doc.get(k) or {} for k in ("lanes", "conflicts", "curves", "regions")}


def resolve_lane(world, name, spec):
    """One lane anchor's attributes (see the module's docstring)."""
    if not isinstance(spec, dict) or not isinstance(spec.get("lanelets"), list) \
            or not spec["lanelets"]:
        raise AnchorError(f"lane {name}: {{lanelets: [<id>, ...]}}")
    ids = []
    for raw in spec["lanelets"]:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            raise AnchorError(f"lane {name}: lanelet {raw!r} is not an id") from None
        if ids[-1] not in world.lanelets:
            raise AnchorError(f"lane {name}: lanelet {ids[-1]} is not in map {world.name}")
    for a, b in zip(ids, ids[1:]):
        if b not in world.lanelets[a].get("following", []):
            raise AnchorError(f"lane {name}: lanelet {b} does not follow {a} in map {world.name} "
                              f"(its followers: {world.lanelets[a].get('following', [])})")
    spans, s0 = [], 0.0
    for i in ids:
        ln = world.length(i)
        spans.append({"id": i, "from_s": s0, "to_s": s0 + ln})
        s0 += ln
    length = s0

    def yaw_in(sp, s):
        """The heading at lane position s on span `sp` (its own spline)."""
        spl = world.spline(sp["id"])
        return spl.yaw(min(max(s - sp["from_s"], 0.0), spl.length))

    def yaw(s):
        """SSv2's heading at lane position s: the lanelet whose range holds it, the later one
        at a join."""
        for sp in reversed(spans):
            if s >= sp["from_s"]:
                return yaw_in(sp, s)
        return yaw_in(spans[0], s)

    # every HEADING_STEP, and each join twice: the lanelet before's end, then the one after's
    # start (consecutive lanelets' splines meet at an angle, so no interval may straddle a join);
    # an interval whose linear interpolation is off by more than HEADING_TOLERANCE is halved,
    # down to HEADING_MIN_STEP (a centreline of points 0.25 m apart makes SSv2's spline heading
    # wiggle faster than 0.5 m: Town01's lanelet 42664, 5e-2 rad at a fixed 0.5 m)
    def interval_error(sp, sa, ha, sb, hb):
        e = 0.0
        for f in (0.2, 0.4, 0.6, 0.8):
            e = max(e, abs(_wrap(ha + f * _wrap(hb - ha) - yaw_in(sp, sa + f * (sb - sa)))))
        return e

    def refine(sp, sa, ha, sb, hb, out, err):
        e = interval_error(sp, sa, ha, sb, hb)
        if e > HEADING_TOLERANCE and sb - sa > 2 * HEADING_MIN_STEP:
            sm = (sa + sb) / 2
            hm = yaw_in(sp, sm)
            err = refine(sp, sa, ha, sm, hm, out, err)
            out.append((sm, hm))
            return refine(sp, sm, hm, sb, hb, out, err)
        return max(err, e)

    def tangent_yaw(curve, t):
        tx, ty, _ = curve.tangent(t)
        return math.atan2(ty, tx)

    # each lanelet's spline is a chain of curves, one between each pair of its points, whose
    # tangents need not meet at the points: each curve is tabled on its own, so a curve's
    # boundary is listed twice too (the end of the one before, the start of the one after)
    ss, heading, err = [], [], 0.0
    for sp in spans:
        spl = world.spline(sp["id"])
        c0 = sp["from_s"]
        for curve, ln in zip(spl.curves, spl.lengths):
            a, b = c0, c0 + ln
            c0 = b
            if ln < 1e-12:
                continue
            k0 = int(math.ceil(a / HEADING_STEP - 1e-9))
            inner = [k * HEADING_STEP for k in range(k0, int(math.floor(b / HEADING_STEP)) + 1)
                     if a + 1e-9 < k * HEADING_STEP < b - 1e-9]
            base = [(a, tangent_yaw(curve, 0.0))] + [(q, yaw_in(sp, q)) for q in inner] \
                + [(b, tangent_yaw(curve, 1.0))]
            pts = [base[0]]
            for (qa, ha), (qb, hb) in zip(base, base[1:]):
                extra = []
                err = refine(sp, qa, ha, qb, hb, extra, err)
                pts += extra + [(qb, hb)]
            for q, h in pts:
                if ss and abs(q - ss[-1]) < 1e-12 and abs(_wrap(h - heading[-1])) < 1e-12:
                    continue        # a boundary whose tangents meet: listed once
                ss.append(q)
                heading.append(h)
    first, last = world.spline(ids[0]), world.spline(ids[-1])
    x0, y0, _ = first.point(0.0)
    x1, y1, _ = last.point(last.length)
    # the centreline at the same s (092 K9's knob profiles along a lane: the ego is placed on
    # the lane by projecting it onto this polyline)
    xy = [_lane_point(world, {"lanelets": spans}, q) for q in ss]
    return {"kind": "lane", "lanelets": spans, "length": length,
            "speed_limit": min(float(world.lanelets[i]["speed_limit"]) for i in ids),
            "start_x": x0, "start_y": y0, "end_x": x1, "end_y": y1,
            "heading_s": ss, "heading": heading, "heading_max_error": err,
            "x": [p[0] for p in xy], "y": [p[1] for p in xy]}


def _lane_point(world, lane, s):
    """A resolved lane's centreline point at lane position s (its spans, SSv2's splines)."""
    for sp in reversed(lane["lanelets"]):
        if s >= sp["from_s"]:
            break
    spl = world.spline(sp["id"])
    x, y, _ = spl.point(min(max(s - sp["from_s"], 0.0), spl.length))
    return x, y


def _crossings(world, a, b, a0=0.0, a1=None, b0=0.0, b1=None, step=CONFLICT_STEP):
    """[(s_a, s_b)] where lane a's centreline crosses lane b's, sampled every `step` m over
    [a0, a1] and [b0, b1]: the segment intersections of the two polylines."""
    a1 = a["length"] if a1 is None else a1
    b1 = b["length"] if b1 is None else b1

    def poly(lane, s0, s1):
        n = max(1, int(math.ceil((s1 - s0) / step)))
        ss = [s0 + (s1 - s0) * k / n for k in range(n + 1)]
        return ss, [_lane_point(world, lane, s) for s in ss]
    sa, pa = poly(a, a0, a1)
    sb, pb = poly(b, b0, b1)
    out = []
    for i in range(len(pa) - 1):
        (x1, y1), (x2, y2) = pa[i], pa[i + 1]
        for j in range(len(pb) - 1):
            (x3, y3), (x4, y4) = pb[j], pb[j + 1]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(den) < 1e-12:
                continue
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
            if 0.0 <= t < 1.0 and 0.0 <= u < 1.0:
                out.append((sa[i] + t * (sa[i + 1] - sa[i]), sb[j] + u * (sb[j + 1] - sb[j])))
    return out


def resolve_conflict(world, name, spec, lanes):
    """A conflict point: where two declared lanes' centrelines cross (exactly once). Its
    position in each lane (`s_<lane>`, SSv2's arc length), its map point, the angle between the
    lanes there (rad, the second's heading less the first's, wrapped), and how far apart the two
    centrelines' points are at those s (`position_error`, m)."""
    if not isinstance(spec, dict) or not isinstance(spec.get("lanes"), list) \
            or len(spec["lanes"]) != 2 or spec["lanes"][0] == spec["lanes"][1]:
        raise AnchorError(f"conflict {name}: {{lanes: [<lane>, <other lane>]}}, two lanes this "
                          f"file declares")
    na, nb = spec["lanes"]
    for n in (na, nb):
        if n not in lanes or lanes[n].get("kind") != "lane":
            raise AnchorError(f"conflict {name}: {n!r} is not a lane this file declares")
    a, b = lanes[na], lanes[nb]
    coarse = _crossings(world, a, b)
    if len(coarse) != 1:
        raise AnchorError(f"conflict {name}: lanes {na} and {nb} cross {len(coarse)} times; a "
                          f"conflict is one crossing (shorten a lane to the part that crosses)")
    s_a, s_b = coarse[0]
    w = 2 * CONFLICT_STEP
    fine = _crossings(world, a, b, max(0.0, s_a - w), min(a["length"], s_a + w),
                      max(0.0, s_b - w), min(b["length"], s_b + w), step=CONFLICT_FINE)
    if fine:
        s_a, s_b = min(fine, key=lambda p: abs(p[0] - s_a) + abs(p[1] - s_b))
    xa, ya = _lane_point(world, a, s_a)
    xb, yb = _lane_point(world, b, s_b)

    def yaw(lane, s):
        for sp in reversed(lane["lanelets"]):
            if s >= sp["from_s"]:
                break
        spl = world.spline(sp["id"])
        return spl.yaw(min(max(s - sp["from_s"], 0.0), spl.length))
    return {"kind": "conflict", "lanes": [na, nb], f"s_{na}": s_a, f"s_{nb}": s_b,
            "x": (xa + xb) / 2, "y": (ya + yb) / 2,
            "angle": _wrap(yaw(b, s_b) - yaw(a, s_a)),
            "position_error": math.hypot(xa - xb, ya - yb)}


def _lane_yaw(world, lane, s):
    for sp in reversed(lane["lanelets"]):
        if s >= sp["from_s"]:
            break
    spl = world.spline(sp["id"])
    return spl.yaw(min(max(s - sp["from_s"], 0.0), spl.length))


def _lane_of(kind, name, spec, lanes):
    n = spec.get("lane") if isinstance(spec, dict) else None
    if n not in lanes:
        raise AnchorError(f"{kind} {name}: lane {n!r} is not a lane this file declares")
    return n, lanes[n]


def resolve_curve(world, name, spec, lanes):
    """A curve: a stretch of a declared lane, `{lane, from_s, to_s}`. Its `length`, `turn` (rad,
    the heading's change over it, positive left), `direction` (left or right), `min_radius` (m,
    the tightest CURVE_WINDOW of it), `mean_radius` (length over turn; both null for a
    straight) and its ends' s."""
    n, lane = _lane_of("curve", name, spec, lanes)
    try:
        a, b = float(spec["from_s"]), float(spec["to_s"])
    except (KeyError, TypeError, ValueError):
        raise AnchorError(f"curve {name}: {{lane, from_s, to_s}}, numbers") from None
    if not (0.0 <= a < b <= lane["length"] + 1e-9):
        raise AnchorError(f"curve {name}: from_s {a} and to_s {b} are not a stretch of lane {n} "
                          f"[0, {lane['length']:.3f}] m")
    k = max(1, int(math.ceil((b - a) / CURVE_STEP)))
    ss = [a + (b - a) * i / k for i in range(k + 1)]
    hs = [_lane_yaw(world, lane, s) for s in ss]
    cum = [0.0]
    for i in range(k):
        cum.append(cum[-1] + _wrap(hs[i + 1] - hs[i]))
    turn = cum[-1]
    w = max(1, min(k, int(round(CURVE_WINDOW / ((b - a) / k)))))
    kappa = max(abs(cum[i + w] - cum[i]) / (ss[i + w] - ss[i]) for i in range(k - w + 1))
    return {"kind": "curve", "lane": n, "from_s": a, "to_s": b, "length": b - a, "turn": turn,
            "direction": "left" if turn > 0 else "right",
            "min_radius": (1.0 / kappa) if kappa > 1e-9 else None,
            "mean_radius": ((b - a) / abs(turn)) if abs(turn) > 1e-9 else None}


def _inside(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def resolve_region(world, name, spec, lanes):
    """A region: a polygon in the map frame, `{polygon: [[x, y], ...]}` (three or more corners).
    Its `area`, centroid `x` and `y`, and for each declared lane that enters it once the lane
    positions where it enters and leaves (`from_<lane>`, `to_<lane>`, sampled every
    REGION_STEP m)."""
    poly = spec.get("polygon") if isinstance(spec, dict) else None
    try:
        poly = [(float(p[0]), float(p[1])) for p in poly]
    except (TypeError, ValueError, IndexError, KeyError):
        poly = None
    if not poly or len(poly) < 3:
        raise AnchorError(f"region {name}: {{polygon: [[x, y], ...]}}, three or more corners")
    a2 = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))
    if abs(a2) < 1e-9:
        raise AnchorError(f"region {name}: its polygon has no area")
    cx = sum((x1 + x2) * (x1 * y2 - x2 * y1)
             for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / (3 * a2)
    cy = sum((y1 + y2) * (x1 * y2 - x2 * y1)
             for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / (3 * a2)
    out = {"kind": "region", "polygon": [list(p) for p in poly], "area": abs(a2) / 2,
           "x": cx, "y": cy}
    for n, lane in lanes.items():
        k = max(1, int(math.ceil(lane["length"] / REGION_STEP)))
        ss = [lane["length"] * i / k for i in range(k + 1)]
        ins = [_inside(poly, *_lane_point(world, lane, s)) for s in ss]
        runs, start = [], None
        for s, i in zip(ss, ins):
            if i and start is None:
                start = s
            if not i and start is not None:
                runs.append((start, s))
                start = None
        if start is not None:
            runs.append((start, ss[-1]))
        if len(runs) == 1:
            out[f"from_{n}"], out[f"to_{n}"] = runs[0]
    return out


def resolve(map_dir, export):
    """The resolved document for `<map dir>/anchors.yaml`, from the map's export (its digest
    checked against the map)."""
    from .world_lanelet import LaneletWorld   # torch: the author's side only
    map_dir = Path(map_dir)
    decl = map_dir / DECLARATION
    if not decl.is_file():
        raise AnchorError(f"{map_dir}: no {DECLARATION}")
    world = LaneletWorld.load(export, map_dir=map_dir)
    decl_doc = _declaration(decl)
    anchors = {name: resolve_lane(world, name, spec)
               for name, spec in decl_doc["lanes"].items()}
    lanes = dict(anchors)
    for kind, fn in (("conflict", resolve_conflict), ("curve", resolve_curve),
                     ("region", resolve_region)):
        for name, spec in decl_doc[kind + "s"].items():
            if name in anchors:
                raise AnchorError(f"{kind} {name}: another anchor has that name")
            anchors[name] = fn(world, name, spec, lanes)
    return {"format": FORMAT, "version": VERSION, "map": map_dir.name,
            "map_sha256": map_export.map_digest(map_dir),
            "declaration_sha256": hashlib.sha256(decl.read_bytes()).hexdigest(),
            "heading_step": HEADING_STEP, "heading_tolerance": HEADING_TOLERANCE,
            "heading_min_step": HEADING_MIN_STEP,
            "heading_max_error": max([a["heading_max_error"] for a in anchors.values()
                                      if "heading_max_error" in a], default=0.0),
            "anchors": anchors}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m scensim_batch.anchors",
                                 description="resolve a map's anchors (its author, once)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve", help="anchors.yaml -> anchors.resolved.json, beside the map")
    r.add_argument("map_dir")
    r.add_argument("--export", required=True, help="the map's export (scensim_batch.map_export)")
    r.add_argument("-o", "--output", help=f"default: <map dir>/{RESOLVED}")
    a = ap.parse_args(argv)
    try:
        doc = resolve(a.map_dir, a.export)
    except (AnchorError, ValueError, FileNotFoundError) as e:
        print(f"anchors: {e}", file=sys.stderr)
        return 2
    out = Path(a.output) if a.output else Path(a.map_dir) / RESOLVED
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{out}: {len(doc['anchors'])} anchor(s), heading error at most "
          f"{doc['heading_max_error']:.2e} rad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
