"""A Lanelet2 map as the batch's world (roadmap 092 K2.6): what SSv2's traffic simulator reads
of a map, exported once, in system Python with lanelet2, for a batch that runs where lanelet2
is not (Isaac's Python):

    python3 -m scensim_batch.map_export <map dir> -o <file.json>

The file (`FORMAT`, version `VERSION`) is JSON:

    {"format": "scensim-batch-lanelet-map", "version": 3,
     "centerline": "ssv2-fine-2.0", "use_custom_centerline": true,
     "map": "<the map directory's name>", "map_sha256": "<map_digest(map dir)>",
     "frame": "map",
     "lanelets": {"<id>": {
         "centerline": [[x, y, z], ...],   # SSv2's centre points: its own 2 m line
                                           # (`ssv2_centerline`, issue 194) unless the lanelet
                                           # has a custom one; a 2-point one with its midpoint
         "left_bound": [[x, y], ...],      # its bounds, for which lanelets are near a point
         "right_bound": [[x, y], ...],     # (SSv2's nearbyLaneletIds)
         "subtype": "road",                # the lanelet's subtype tag, null without one (SSv2's
                                           # nearby search drops those and crosswalks)
         "turn_direction": "straight",     # its turn_direction tag, "else" without one
         "following": [<id>, ...],         # the vehicle routing graph's following(), in SSv2's order
         "previous": [<id>, ...],
         "left": <id> | null,              # the graph's left(): a lane change may go there
         "right": <id> | null,
         "adjacent_left": <id> | null,     # adjacentLeft(): beside it, changeable or not
         "adjacent_right": <id> | null,
         "speed_limit": 13.89,             # m/s, lanelet2's (Germany, vehicle; 50 km/h untagged)
         "speed_limit_tagged": true}}}

The routing graph is lanelet2's for Germany's vehicle rules, as SSv2's VEHICLE graph. A
lanelet's length and every query on its centreline are the adapter's (world_lanelet.py: SSv2's
Catmull-Rom spline through these points), not the file's, so the file holds only what the map
says. `map_sha256` is `map_digest`, over the files that decide the geometry; the adapter
refuses an export whose digest is not the map's in use.
"""
import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FORMAT = "scensim-batch-lanelet-map"
VERSION = 3     # 2: `following`/`previous` in SSv2's order (a graph on the map as parsed);
                # 3: SSv2's own centreline (issue 194)
LINE = "ssv2-fine-2.0"          # the centre points' source: SSv2's generateFineCenterline, 2 m
USE_CUSTOM_CENTERLINE = True    # scenario_test_runner's launch default, which scensim keeps
RESOLUTION = 2.0                # m, LaneletLoader::overwriteLaneletsCenterline's


class ExportError(ValueError):
    pass


def _accumulated(points):
    out = [0.0]
    for a, b in zip(points, points[1:]):
        out.append(out[-1] + math.dist(a, b))      # 3D, as lanelet2's distance on Point3d
    return out


def _resample(points, n, where):
    """SSv2's LaneletLoader::resamplePoints (lanelet_loader.cpp, fork 31b12c5f), its order and
    arithmetic kept: n + 1 points at equal 3D arc length along `points`."""
    acc = _accumulated(points)
    total = acc[-1]                                # lanelet2's geometry::length, 3D
    N = len(acc)
    out = []
    for i in range(n + 1):
        t = (i / n) * total
        # findNearestIndexPair: below acc[1], above acc[N-2], else the first segment holding t
        if t < acc[1]:
            j = 0
        elif t > acc[N - 2]:
            j = N - 2
        else:
            j = next(k - 1 for k in range(1, N) if acc[k - 1] <= t <= acc[k])
        back, front = points[j], points[j + 1]
        seg = acc[j + 1] - acc[j]
        if seg == 0.0:   # unreachable after the refusals below; SSv2 would divide 0 by 0
            raise ExportError(f"{where}: a zero-length segment at point {j}")
        out.append([back[d] + (front[d] - back[d]) * (t - acc[j]) / seg for d in range(3)])
    return out


def ssv2_centerline(left, right, where="lanelet"):
    """SSv2's generateFineCenterline: both bounds resampled into max(ceil(longer / 2.0), 1)
    equal 3D segments, averaged pairwise, z included. Refused (ExportError, naming `where` and
    the bound) where SSv2 cannot resample: a bound of fewer than 2 points (SSv2 throws) or with
    consecutive duplicate points (SSv2 can pick that zero-length segment: NaN)."""
    bounds = {"left": [tuple(map(float, p)) for p in left],
              "right": [tuple(map(float, p)) for p in right]}
    for side, pts in bounds.items():
        if len(pts) < 2:
            raise ExportError(f"{where}: its {side} bound has {len(pts)} point(s); SSv2 "
                              "needs 2 (it throws)")
        for k, (a, b) in enumerate(zip(pts, pts[1:])):
            if a == b:
                raise ExportError(f"{where}: its {side} bound repeats point {k} at {k + 1}; "
                                  "SSv2 would resample a zero-length segment (NaN)")
    longer = max(_accumulated(bounds["left"])[-1], _accumulated(bounds["right"])[-1])
    n = max(int(math.ceil(longer / RESOLUTION)), 1)
    lft = _resample(bounds["left"], n, f"{where} left")
    rgt = _resample(bounds["right"], n, f"{where} right")
    return [[(a + b) / 2.0 for a, b in zip(p, q)] for p, q in zip(rgt, lft)]


def custom_centerlines(osm):
    """Ids of the lanelets with a custom centreline: lanelet2's hasCustomCenterline (a member
    with role `centerline`), read from the OSM, as the Python binding does not expose it."""
    out = set()
    for _, el in ET.iterparse(str(osm), events=("end",)):
        if el.tag == "relation":
            if any(m.get("role") == "centerline" for m in el.iter("member")):
                out.add(int(el.get("id")))
            el.clear()
        elif el.tag in ("node", "way"):
            el.clear()
    return out

DIGEST_FILES = ("lanelet2_map.osm", "map_projector_info.yaml")


def map_digest(map_dir):
    """sha256 over the map's `lanelet2_map.osm` and `map_projector_info.yaml` (when there), each
    as its name, a NUL and its bytes: what fixes the lanelets' points in the map frame."""
    d = Path(map_dir)
    if not (d / "lanelet2_map.osm").is_file():
        raise FileNotFoundError(f"{d}: no lanelet2_map.osm")
    h = hashlib.sha256()
    for name in DIGEST_FILES:
        p = d / name
        if p.is_file():
            h.update(name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def _centre_points(ll, custom=frozenset()):
    """SSv2's centre points of `ll`: its custom centreline when it has one (SSv2 keeps it with
    use_custom_centerline true), else SSv2's own 2 m line; then CenterPointsCache's midpoint."""
    if int(ll.id) in custom and USE_CUSTOM_CENTERLINE:
        pts = [[float(p.x), float(p.y), float(p.z)] for p in ll.centerline]
    else:
        pts = ssv2_centerline([(p.x, p.y, p.z) for p in ll.leftBound],
                              [(p.x, p.y, p.z) for p in ll.rightBound], f"lanelet {ll.id}")
    return midpoint(pts)


def midpoint(pts):
    """SSv2's CenterPointsCache::centerPoints: a 2-point line gets its midpoint (a curve of
    three); with SSv2's own line that is when the longer bound is 2.0 m or less."""
    pts = [list(p) for p in pts]
    if len(pts) == 2:     # SSv2's CenterPointsCache: a midpoint makes it a curve of three
        (x0, y0, z0), (x2, y2, z2) = pts
        pts.insert(1, [(x0 + x2) * 0.5, (y0 + y2) * 0.5, (z0 + z2) * 0.5])
    return pts


def _id(ll):
    return None if ll is None else int(ll.id)


def topology_graph(map_dir):
    """(map, routing graph) on the map as lanelet2 parses it, for the order of `following()`
    and `previous()`: SSv2 takes a route-less NPC's turn as the first of them, and lanelet2's
    order is the one its graph builder finds on the parsed map. simple_route's map has its
    points moved to the map frame before its graph is built, which reorders 20 of Town01's 36
    branches (checked against SSv2's own lanelet_wrapper); a graph on any fresh parse orders
    all 36 as SSv2 does. The projector does not matter (UTM, local cartesian and Mercator
    agree); local cartesian accepts any origin."""
    import lanelet2
    from lanelet2.io import Origin
    from lanelet2.projection import LocalCartesianProjector
    from scensim_agent.adapters.simple_route import _osm_nodes, parse_origin, read_projector_info

    osm = Path(map_dir) / "lanelet2_map.osm"
    lat, lon = parse_origin(read_projector_info(osm.parent), _osm_nodes(osm))
    m = lanelet2.io.load(str(osm), LocalCartesianProjector(Origin(lat, lon)))
    rules = lanelet2.traffic_rules.create(lanelet2.traffic_rules.Locations.Germany,
                                          lanelet2.traffic_rules.Participants.Vehicle)
    return m, lanelet2.routing.RoutingGraph(m, rules)


def export(map_dir):
    """The export of `map_dir` (a dict, FORMAT version VERSION)."""
    from scensim_agent.adapters.simple_route import load_map

    d = Path(map_dir)
    lmap, rules, graph = load_map(d)
    tmap, tgraph = topology_graph(d)
    custom = custom_centerlines(d / "lanelet2_map.osm")
    out = {}
    for ll in sorted(lmap.laneletLayer, key=lambda x: x.id):
        attrs = ll.attributes
        tagged = "speed_limit" in attrs
        try:
            limit = float(rules.speedLimit(ll).speedLimit) / 3.6   # lanelet2 gives km/h
        except Exception:   # noqa: BLE001 - a malformed tag: lanelet2's urban default
            limit, tagged = 50.0 / 3.6, False
        out[str(ll.id)] = {
            "centerline": _centre_points(ll, custom),
            "left_bound": [[float(p.x), float(p.y)] for p in ll.leftBound],
            "right_bound": [[float(p.x), float(p.y)] for p in ll.rightBound],
            "subtype": attrs["subtype"] if "subtype" in attrs else None,
            "turn_direction": attrs["turn_direction"] if "turn_direction" in attrs else "else",
            "following": [int(x.id) for x in tgraph.following(tmap.laneletLayer[ll.id])],
            "previous": [int(x.id) for x in tgraph.previous(tmap.laneletLayer[ll.id])],
            "left": _id(graph.left(ll)),
            "right": _id(graph.right(ll)),
            "adjacent_left": _id(graph.adjacentLeft(ll)),
            "adjacent_right": _id(graph.adjacentRight(ll)),
            "speed_limit": limit,
            "speed_limit_tagged": tagged,
        }
    return {"format": FORMAT, "version": VERSION, "centerline": LINE,
            "use_custom_centerline": USE_CUSTOM_CENTERLINE, "map": d.resolve().name,
            "map_sha256": map_digest(d), "frame": "map", "lanelets": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("map_dir")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args(argv)
    doc = export(a.map_dir)
    Path(a.output).write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    print(json.dumps({"map": doc["map"], "lanelets": len(doc["lanelets"]),
                      "map_sha256": doc["map_sha256"], "output": a.output}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
