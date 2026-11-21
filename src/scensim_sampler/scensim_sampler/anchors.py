"""A world's anchors as the sampler reads them (roadmap 092 K9a; scenario-description.md 2a gap 7
and section 3), with nothing but the standard library: no lanelet2, no torch.

Two sources, merged by name (a name in both is refused):

- the project's own, `testbench.yaml`'s `world.anchors`: stated numbers, {name: {kind, <attr>:
  number}} (gap 7);
- the map's, `<map dir>/anchors.resolved.json`, which the map's author makes once with
  `python3 -m scensim_batch.anchors resolve` (it needs torch) from the map's `anchors.yaml`.
  Its `map_sha256` must be the map's in use (`map_digest`, as scensim_batch.map_export's).

An expression reads `anchor.<name>.<attribute>`; a resolved lane's heading is read at an arc
position, `anchor.<name>.heading(s)`, interpolated from the file's table (its error at most the
file's `heading_max_error`); a bare `heading` is only a stated anchor's number.
"""
import hashlib
import json
import math
from pathlib import Path

FORMAT = "scensim-anchors"
VERSION = 1
RESOLVED = "anchors.resolved.json"
DIGEST_FILES = ("lanelet2_map.osm", "map_projector_info.yaml")   # scensim_batch.map_export's
LANE_NUMBERS = ("length", "speed_limit", "start_x", "start_y", "end_x", "end_y")


class AnchorError(ValueError):
    pass


def map_digest(map_dir):
    """scensim_batch.map_export.map_digest, without importing scensim_batch (torch)."""
    d = Path(map_dir)
    if not (d / "lanelet2_map.osm").is_file():
        raise AnchorError(f"{d}: no lanelet2_map.osm")
    h = hashlib.sha256()
    for name in DIGEST_FILES:
        p = d / name
        if p.is_file():
            h.update(name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def load_resolved(path, map_dir=None):
    """{name: anchor} from a resolved file; with `map_dir`, refused unless it was resolved on
    that map (its digest)."""
    path = Path(path)
    doc = json.loads(path.read_text())
    if doc.get("format") != FORMAT or doc.get("version") != VERSION:
        raise AnchorError(f"{path}: not a {FORMAT} v{VERSION} file")
    if map_dir is not None:
        want = map_digest(map_dir)
        if doc.get("map_sha256") != want:
            raise AnchorError(f"{path}: resolved on map {doc.get('map')} "
                              f"{str(doc.get('map_sha256'))[:12]}, not the map in use "
                              f"({want[:12]}): its author resolves it again "
                              "(python3 -m scensim_batch.anchors resolve)")
    out = {}
    for name, a in (doc.get("anchors") or {}).items():
        out[name] = dict(a, source={"map": doc.get("map"), "map_sha256": doc.get("map_sha256"),
                                    "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return out


def merge(stated=None, resolved=None):
    """The project's stated anchors and the map's resolved ones, by name; one name in both is
    refused rather than either silently winning."""
    stated, resolved = dict(stated or {}), dict(resolved or {})
    both = sorted(set(stated) & set(resolved))
    if both:
        raise AnchorError(f"anchor(s) {', '.join(both)}: declared by the map's anchors file and "
                          "by testbench.yaml world.anchors; keep one")
    return {**resolved, **stated}


class Heading:
    """A resolved lane's heading table, called with an arc position."""

    def __init__(self, name, s, h, length):
        self.name, self.s, self.h, self.length = name, list(s), list(h), float(length)

    def __call__(self, s):
        s = float(s)
        if not (-1e-9 <= s <= self.length + 1e-9):
            raise AnchorError(f"anchor.{self.name}.heading({s}): s outside the lane's "
                              f"[0, {self.length:.3f}] m")
        ss = self.s
        lo, hi = 0, len(ss) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ss[mid] <= s:
                lo = mid
            else:
                hi = mid
        if hi == lo or ss[hi] == ss[lo]:
            return self.h[lo]
        f = (s - ss[lo]) / (ss[hi] - ss[lo])
        d = math.atan2(math.sin(self.h[hi] - self.h[lo]), math.cos(self.h[hi] - self.h[lo]))
        return math.atan2(math.sin(self.h[lo] + f * d), math.cos(self.h[lo] + f * d))


def env(anchors):
    """({"anchor.<name>.<attr>": number}, {"anchor.<name>.<attr>": callable}) for expressions:
    a stated anchor's numbers; a resolved lane's numbers, its start heading, and heading(s)."""
    numbers, functions = {}, {}
    for name, a in (anchors or {}).items():
        if not isinstance(a, dict):
            raise AnchorError(f"anchor {name}: {{attribute: value}}, not {a!r}")
        if "heading_s" in a:        # resolved
            for k in LANE_NUMBERS:
                numbers[f"anchor.{name}.{k}"] = float(a[k])
            functions[f"anchor.{name}.heading"] = Heading(name, a["heading_s"], a["heading"],
                                                          a["length"])
            continue
        for k, v in a.items():
            if k == "kind":
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise AnchorError(f"anchor {name}.{k}: a number, not {v!r}")
            numbers[f"anchor.{name}.{k}"] = float(v)
    return numbers, functions


def sources(anchors, read):
    """{map, map_sha256, file_sha256} of each resolved file the names in `read` came from."""
    out = []
    for dotted in read:
        name = dotted.split(".")[1]
        src = (anchors.get(name) or {}).get("source")
        if src and src not in out:
            out.append(src)
    return out
