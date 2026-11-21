"""A Lanelet2 map as the batch's world (roadmap 092 K2.6): what SSv2's traffic simulator reads
of a map, exported once, in system Python with lanelet2, for a batch that runs where lanelet2
is not (Isaac's Python):

    python3 -m scensim_batch.map_export <map dir> -o <file.json>

The file (`FORMAT`, version `VERSION`) is JSON:

    {"format": "scensim-batch-lanelet-map", "version": 1,
     "map": "<the map directory's name>", "map_sha256": "<map_digest(map dir)>",
     "frame": "map",
     "lanelets": {"<id>": {
         "centerline": [[x, y, z], ...],   # SSv2's centre points: lanelet2's centerline(), a
                                           # 2-point one with its midpoint inserted
         "left_bound": [[x, y], ...],      # its bounds, for which lanelets are near a point
         "right_bound": [[x, y], ...],     # (SSv2's nearbyLaneletIds)
         "subtype": "road",                # the lanelet's subtype tag, null without one (SSv2's
                                           # nearby search drops those and crosswalks)
         "turn_direction": "straight",     # its turn_direction tag, "else" without one
         "following": [<id>, ...],         # the vehicle routing graph's following(), in order
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
import sys
from pathlib import Path

FORMAT = "scensim-batch-lanelet-map"
VERSION = 1
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


def _centre_points(ll):
    pts = [[float(p.x), float(p.y), float(p.z)] for p in ll.centerline]
    if len(pts) == 2:     # SSv2's CenterPointsCache: a midpoint makes it a curve of three
        (x0, y0, z0), (x2, y2, z2) = pts
        pts.insert(1, [(x0 + x2) * 0.5, (y0 + y2) * 0.5, (z0 + z2) * 0.5])
    return pts


def _id(ll):
    return None if ll is None else int(ll.id)


def export(map_dir):
    """The export of `map_dir` (a dict, FORMAT version VERSION)."""
    from scensim_agent.adapters.simple_route import load_map

    d = Path(map_dir)
    lmap, rules, graph = load_map(d)
    out = {}
    for ll in sorted(lmap.laneletLayer, key=lambda x: x.id):
        attrs = ll.attributes
        tagged = "speed_limit" in attrs
        try:
            limit = float(rules.speedLimit(ll).speedLimit) / 3.6   # lanelet2 gives km/h
        except Exception:   # noqa: BLE001 - a malformed tag: lanelet2's urban default
            limit, tagged = 50.0 / 3.6, False
        out[str(ll.id)] = {
            "centerline": _centre_points(ll),
            "left_bound": [[float(p.x), float(p.y)] for p in ll.leftBound],
            "right_bound": [[float(p.x), float(p.y)] for p in ll.rightBound],
            "subtype": attrs["subtype"] if "subtype" in attrs else None,
            "turn_direction": attrs["turn_direction"] if "turn_direction" in attrs else "else",
            "following": [int(x.id) for x in graph.following(ll)],
            "previous": [int(x.id) for x in graph.previous(ll)],
            "left": _id(graph.left(ll)),
            "right": _id(graph.right(ll)),
            "adjacent_left": _id(graph.adjacentLeft(ll)),
            "adjacent_right": _id(graph.adjacentRight(ll)),
            "speed_limit": limit,
            "speed_limit_tagged": tagged,
        }
    return {"format": FORMAT, "version": VERSION, "map": d.resolve().name,
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
