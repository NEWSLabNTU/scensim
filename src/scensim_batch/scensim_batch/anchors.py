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

A lane resolves to its `length` (m: the sum of its lanelets' SSv2 splines, world_lanelet's
Catmull-Rom, so an s here is an s in a LanePosition), `speed_limit` (m/s, the lowest of its
lanelets'), `start_x`, `start_y`, `end_x`, `end_y`, its lanelets with their s ranges, and
`heading` (rad, the map frame) at `heading_s`: every `HEADING_STEP` m within each lanelet, and
each lanelet's start and end, so a join between two lanelets is listed twice (the end of the
one before, then the start of the one after: their splines meet at an angle, and no interval
straddles it), and likewise each boundary between the curves of a lanelet's spline (SSv2's
Catmull-Rom is a chain of curves whose tangents need not meet); an interval whose linear interpolation is off by more than `HEADING_TOLERANCE`
is halved, down to `HEADING_MIN_STEP`. `heading_max_error` is the largest difference between
that table, interpolated linearly, and the spline's heading at four points inside each
interval: at most the tolerance unless the minimum step stopped a halving.
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
KINDS_LATER = ("points", "conflicts", "regions", "curves")   # 092 K9c


class AnchorError(ValueError):
    pass


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _declaration(path):
    doc = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(doc, dict) or doc.get("anchors") != 1:
        raise AnchorError(f"{path}: not an anchors file (anchors: 1)")
    unknown = sorted(set(doc) - {"anchors", "lanes"} - set(KINDS_LATER))
    if unknown:
        raise AnchorError(f"{path}: unknown section(s) {', '.join(unknown)} (lanes; "
                          f"{', '.join(KINDS_LATER)} come with 092 K9c)")
    later = [k for k in KINDS_LATER if doc.get(k)]
    if later:
        raise AnchorError(f"{path}: {', '.join(later)}: not resolved yet (092 K9c); lanes only")
    return doc.get("lanes") or {}


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
    return {"kind": "lane", "lanelets": spans, "length": length,
            "speed_limit": min(float(world.lanelets[i]["speed_limit"]) for i in ids),
            "start_x": x0, "start_y": y0, "end_x": x1, "end_y": y1,
            "heading_s": ss, "heading": heading, "heading_max_error": err}


def resolve(map_dir, export):
    """The resolved document for `<map dir>/anchors.yaml`, from the map's export (its digest
    checked against the map)."""
    from .world_lanelet import LaneletWorld   # torch: the author's side only
    map_dir = Path(map_dir)
    decl = map_dir / DECLARATION
    if not decl.is_file():
        raise AnchorError(f"{map_dir}: no {DECLARATION}")
    world = LaneletWorld.load(export, map_dir=map_dir)
    lanes = _declaration(decl)
    anchors = {name: resolve_lane(world, name, spec) for name, spec in lanes.items()}
    return {"format": FORMAT, "version": VERSION, "map": map_dir.name,
            "map_sha256": map_export.map_digest(map_dir),
            "declaration_sha256": hashlib.sha256(decl.read_bytes()).hexdigest(),
            "heading_step": HEADING_STEP, "heading_tolerance": HEADING_TOLERANCE,
            "heading_min_step": HEADING_MIN_STEP,
            "heading_max_error": max([a["heading_max_error"] for a in anchors.values()],
                                     default=0.0),
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
