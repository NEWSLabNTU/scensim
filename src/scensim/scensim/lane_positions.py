"""A scenario's LanePositions against the reversed stretches of SSv2's spline (issue 166).

SSv2's lane spline (a uniform Catmull-Rom) runs backward over a short stretch where a lanelet's
centre points change spacing: an entity placed at an s inside one faces about 180 degrees off.
On the lanelets vehicles are routed over the stretches are a few centimetres; on isolated ones
(walkways, kerb lines) they reach metres. `scensim check` refuses a LanePosition whose lanelet
and s are both written in the scenario and whose s lies in a stretch; `scensim run` warns when
the values a run binds (a parameter, a suite's or sampler's value, an anchor) put one there.

The stretches come from the map's lanelets as `scensim_batch.map_export` takes them (SSv2's
centre points) and `scensim_batch.catmull`'s spline, SSv2's ported; no torch.
"""
import functools
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PARAM = re.compile(r"^\$(\w+)$")


def positions(path: Path) -> list:
    """[(laneId, s)] as written in the scenario's LanePositions (literal, or `$name`)."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    return [(lp.get("laneId") or "", lp.get("s") or "") for lp in root.iter("LanePosition")]


@functools.lru_cache(maxsize=4)
def _centre_points(map_dir: str, digest: str) -> dict:
    """{lanelet id: centre points} of a map, once per map bytes."""
    from scensim_batch import map_export   # noqa: PLC0415
    doc = map_export.export(map_dir)
    return {int(k): v["centerline"] for k, v in doc["lanelets"].items()}


@functools.lru_cache(maxsize=4096)
def _stretches_of(map_dir: str, digest: str, lane: int) -> tuple:
    from scensim_batch.catmull import lanelet_stretches   # noqa: PLC0415
    pts = _centre_points(map_dir, digest).get(lane)
    return tuple(lanelet_stretches(pts)) if pts else ()


def stretches(map_dir: Path, lane: int) -> tuple:
    """Lanelet `lane`'s reversed stretches on the map at `map_dir`, ((from_s, to_s), ...)."""
    from scensim_batch import map_export   # noqa: PLC0415
    md = str(Path(map_dir))
    return _stretches_of(md, map_export.map_digest(md), int(lane))


def inside(map_dir: Path, lane, s):
    """The stretch (from_s, to_s) holding lanelet `lane`'s position s, or None."""
    try:
        lane, s = int(float(lane)), float(s)
    except (TypeError, ValueError):
        return None
    for a, b in stretches(map_dir, lane):
        if a <= s <= b:
            return a, b
    return None


def message(lane, s, stretch) -> str:
    a, b = stretch
    return (f"LanePosition laneId {lane} s {float(s):g}: inside a reversed stretch "
            f"[{a:.3f}, {b:.3f}] m of SSv2's spline on lanelet {lane}, where an entity placed "
            f"there faces about 180 degrees off (issue 166)")


def fixed_problems(path: Path, map_dir: Path) -> list:
    """[message] for each LanePosition whose lanelet and s are both literal and in a stretch."""
    out = []
    for lane, s in positions(path):
        if PARAM.match(lane) or PARAM.match(s):
            continue
        st = inside(map_dir, lane, s)
        if st:
            out.append(message(lane, s, st))
    return out


def run_warnings(path: Path, map_dir: Path, values: dict) -> list:
    """[message] for each LanePosition with a `$parameter` lanelet or s that `values` (the
    run's parameters, every declared one with its value) put in a stretch."""
    out = []
    for lane, s in positions(path):
        ml, ms = PARAM.match(lane), PARAM.match(s)
        if not (ml or ms):
            continue
        lv = values.get(ml.group(1)) if ml else lane
        sv = values.get(ms.group(1)) if ms else s
        st = inside(map_dir, lv, sv)
        if st:
            out.append(message(lv, sv, st))
    return out
