"""Prop layouts as a knob (roadmap 092 K9f-b): props a world declares in a file, which a knob
value (`layout: <name>`) adds to the scenario a run executes.

A layout is `layouts/<map>/<name>.yaml` in the testbench (a project's own props), or
`<map dir>/layouts/<name>.yaml` published with the map (props meant to ship with it); a name
in both is refused::

    layout: 1
    props:
      barrier_a:
        category: obstacle                 # OpenSCENARIO miscObjectCategory SSv2 implements
        model: static.prop.streetbarrier   # the MiscObject's name: the simulator's asset key
        mass: 50
        box: {center: [0, 0, 0.55], dimensions: [0.4, 1.2, 1.1]}
        at: {lane: west_street, s: 20, offset: -1.3}   # or {point: <anchor>}
        h: 1.5708                          # rad: relative to the lane, absolute at a point

`scensim run` writes the run's own copy of the scenario (`inject`): each prop a ScenarioObject
(a MiscObject) at the end of Entities and a TeleportAction at the end of the Init's Actions, on
a LanePosition with the literal lanelet and lanelet-local s of its lane anchor, or a
WorldPosition at a point anchor. The props are SSv2's entities, so its verdict and the truth
see them. A knob's zones (092 K9f-a; scensim.zones) go into the same copy, as the Init road
condition's `scensim.zone.<id>.<field>` properties. The same source, layouts, zones and anchors
give a byte-identical copy.
"""
import hashlib
import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

FORMAT = 1
# SSv2's interpreter takes `obstacle` and throws on every other category
# (openscenario_interpreter/src/syntax/misc_object_category.cpp)
CATEGORIES = ("obstacle",)
PROP_KEYS = ("category", "model", "mass", "box", "at", "h")
COPY = "scenario.xosc"


class LayoutError(ValueError):
    pass


def find(project: Path, map_name: str, name: str) -> Path:
    """The file of layout `name` for map `map_name`: the testbench's or the map's, not both."""
    own = Path(project) / "layouts" / map_name / f"{name}.yaml"
    shipped = Path(project) / "assets" / "maps" / map_name / "layouts" / f"{name}.yaml"
    have = [p for p in (own, shipped) if p.is_file()]
    if len(have) == 2:
        raise LayoutError(f"layout {name}: in the testbench ({own}) and beside map {map_name} "
                          f"({shipped}); keep one")
    if not have:
        raise LayoutError(f"layout {name}: no layouts/{map_name}/{name}.yaml in the testbench "
                          f"and none beside map {map_name}")
    return have[0]


def read(path: Path) -> dict:
    try:
        doc = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as e:
        raise LayoutError(f"{path}: {e}") from None
    return doc if isinstance(doc, dict) else {}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def problems(doc: dict, anchors: dict, where: str = "layout") -> list:
    """Every way a layout is wrong for a world with `anchors`, as messages."""
    from scensim_sampler import anchors as A  # noqa: PLC0415
    if doc.get("layout") != FORMAT:
        return [f"{where}: `layout: {FORMAT}` first"]
    props = doc.get("props")
    if not isinstance(props, dict) or not props:
        return [f"{where}: props: {{<name>: {{category, model, box, at, h}}}}"]
    try:
        _, functions = A.env(anchors or {})
    except A.AnchorError as e:
        return [f"{where}: {e}"]
    out = []
    for name, p in props.items():
        w = f"{where}: {name}"
        if not isinstance(p, dict):
            out.append(f"{w}: {{category, model, box, at, h}}")
            continue
        bad = sorted(set(p) - set(PROP_KEYS))
        if bad:
            out.append(f"{w}: {bad[0]}: a prop has {', '.join(PROP_KEYS)}")
        if p.get("category") not in CATEGORIES:
            out.append(f"{w}: category {p.get('category')!r}: SSv2 implements "
                       f"{', '.join(CATEGORIES)} only (misc_object_category.cpp)")
        if not isinstance(p.get("model"), str) or not p["model"]:
            out.append(f"{w}: model: the simulator's asset key, a string")
        if p.get("mass") is not None and not (_num(p["mass"]) and p["mass"] > 0):
            out.append(f"{w}: mass: kg, a positive number")
        box = p.get("box")
        if not (isinstance(box, dict) and all(
                isinstance(box.get(k), list) and len(box[k]) == 3 and all(_num(x) for x in box[k])
                for k in ("center", "dimensions"))):
            out.append(f"{w}: box: {{center: [x, y, z], dimensions: [l, w, h]}}")
        if p.get("h") is not None and not _num(p["h"]):
            out.append(f"{w}: h: rad, a number")
        at = p.get("at")
        if isinstance(at, dict) and "lane" in at:
            lane = at["lane"]
            if f"anchor.{lane}.lanelet_at" not in functions:
                out.append(f"{w}: at.lane {lane}: the world has no resolved lane {lane}")
            elif not (_num(at.get("s")) and _num(at.get("offset", 0.0))):
                out.append(f"{w}: at: {{lane, s, offset}}, s and offset numbers")
            else:
                try:
                    functions[f"anchor.{lane}.lanelet_at"](at["s"])
                except A.AnchorError as e:
                    out.append(f"{w}: {e}")
        elif isinstance(at, dict) and "point" in at:
            a = (anchors or {}).get(at["point"])
            if not (isinstance(a, dict) and _num(a.get("x")) and _num(a.get("y"))):
                out.append(f"{w}: at.point {at['point']}: the world has no point anchor with x, y")
        else:
            out.append(f"{w}: at: {{lane, s, offset}} or {{point}}")
    return out


def _lane_xy(a: dict, s: float, offset: float):
    """The map-frame x, y of lane position (s, offset) on a lane resolved with its centreline,
    or None: offset positive to the left of the lane's direction, as OpenSCENARIO's."""
    xs, ys, ss = a.get("x"), a.get("y"), a.get("heading_s")
    if not (xs and ys and ss and len(xs) == len(ss)):
        return None
    i = max(0, min(len(ss) - 2, next((k for k in range(len(ss) - 1) if ss[k + 1] >= s),
                                     len(ss) - 2)))
    f = 0.0 if ss[i + 1] == ss[i] else (s - ss[i]) / (ss[i + 1] - ss[i])
    x = xs[i] + f * (xs[i + 1] - xs[i])
    y = ys[i] + f * (ys[i + 1] - ys[i])
    h = math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i])
    return [x - offset * math.sin(h), y + offset * math.cos(h)]


def place(doc: dict, anchors: dict, where: str = "layout") -> list:
    """Each prop's placement, in name order: {name, category, model, mass, box, h, lanelet, s,
    offset[, x, y]} on a lane, or {..., point, x, y} at a point. LayoutError lists every
    problem."""
    from scensim_sampler import anchors as A  # noqa: PLC0415
    probs = problems(doc, anchors, where)
    if probs:
        raise LayoutError("; ".join(probs))
    _, functions = A.env(anchors or {})
    out = []
    for name in sorted(doc["props"]):
        p = doc["props"][name]
        e = {"name": name, "category": p["category"], "model": p["model"],
             "mass": float(p.get("mass") or 0.0),
             "box": {k: [float(x) for x in p["box"][k]] for k in ("center", "dimensions")},
             "h": float(p.get("h") or 0.0)}
        at = p["at"]
        if "lane" in at:
            s, off = float(at["s"]), float(at.get("offset", 0.0))
            e.update(lane=at["lane"], lane_s=s,
                     lanelet=int(functions[f"anchor.{at['lane']}.lanelet_at"](s)),
                     s=float(functions[f"anchor.{at['lane']}.local_s"](s)), offset=off)
            xy = _lane_xy(anchors[at["lane"]], s, off)
            if xy:
                e.update(x=xy[0], y=xy[1])
        else:
            a = anchors[at["point"]]
            e.update(point=at["point"], x=float(a["x"]), y=float(a["y"]))
        out.append(e)
    return out


def _fmt(v: float) -> str:
    return repr(float(v))


def _absolute(root, source_dir: Path):
    """Relative Directory/LogicFile/SceneGraphFile paths made absolute from the source's
    directory; `$(...)` and `$parameter` values kept."""
    for tag, attr in (("Directory", "path"), ("LogicFile", "filepath"),
                      ("SceneGraphFile", "filepath"), ("ScenarioFile", "filepath")):
        for el in root.iter(tag):
            v = el.get(attr)
            if v and not v.startswith(("$", "/")):
                el.set(attr, os.path.normpath(str(Path(source_dir).resolve() / v)))


def inject(source: Path, placements: list, zone_properties=()) -> bytes:
    """The scenario at `source` with `placements` (place's) added as MiscObject entities and Init
    TeleportActions, and `zone_properties` ([(name, value)], scensim.zones.properties) in its
    Init road condition: the run's copy, the same bytes for the same inputs. LayoutError: a prop
    whose name is already an entity of the source (two writers), or no Entities/Init."""
    root = ET.parse(source).getroot()
    ents = root.find("Entities")
    actions = root.find("Storyboard/Init/Actions")
    if ents is None or actions is None:
        raise LayoutError(f"{source}: no Entities or Storyboard/Init/Actions to add props to")
    have = {so.get("name") for so in ents.iter("ScenarioObject")}
    clash = sorted(have & {p["name"] for p in placements})
    if clash:
        raise LayoutError(f"{Path(source).name}: {', '.join(clash)}: a layout's prop and the "
                          "scenario's entity: two writers, rename one")
    _absolute(root, Path(source).parent)
    for p in placements:
        so = ET.SubElement(ents, "ScenarioObject", {"name": p["name"]})
        mo = ET.SubElement(so, "MiscObject", {"name": p["model"],
                                              "miscObjectCategory": p["category"],
                                              "mass": _fmt(p["mass"])})
        bb = ET.SubElement(mo, "BoundingBox")
        c, d = p["box"]["center"], p["box"]["dimensions"]
        ET.SubElement(bb, "Center", {"x": _fmt(c[0]), "y": _fmt(c[1]), "z": _fmt(c[2])})
        ET.SubElement(bb, "Dimensions", {"length": _fmt(d[0]), "width": _fmt(d[1]),
                                         "height": _fmt(d[2])})
        ET.SubElement(mo, "Properties")
        pr = ET.SubElement(actions, "Private", {"entityRef": p["name"]})
        pos = ET.SubElement(ET.SubElement(ET.SubElement(pr, "PrivateAction"), "TeleportAction"),
                            "Position")
        if "lanelet" in p:
            lp = ET.SubElement(pos, "LanePosition", {"roadId": "", "laneId": str(p["lanelet"]),
                                                     "s": _fmt(p["s"]),
                                                     "offset": _fmt(p["offset"])})
            ET.SubElement(lp, "Orientation", {"type": "relative", "h": _fmt(p["h"])})
        else:
            ET.SubElement(pos, "WorldPosition", {"x": _fmt(p["x"]), "y": _fmt(p["y"]),
                                                 "z": "0.0", "h": _fmt(p["h"]), "p": "0.0",
                                                 "r": "0.0"})
    if zone_properties:
        from scensim import zones as zonesmod  # noqa: PLC0415
        try:
            zonesmod.write(root, list(zone_properties))
        except zonesmod.ZoneError as e:
            raise LayoutError(f"{source}: {e}") from None
    return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(root, encoding="utf-8", xml_declaration=False) + b"\n")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def bound(scenario: Path, parameters: dict, world_knobs: dict) -> dict:
    """{knob: layout name} for the scenario's bound knobs whose value names a layout."""
    from scensim import knobs as knobsmod  # noqa: PLC0415
    out = {}
    for knob, value in knobsmod.bound(scenario, parameters).items():
        decl = (world_knobs or {}).get(knob)
        if not isinstance(decl, dict) or knobsmod.is_profile_knob(decl):
            continue
        m = {str(k): v for k, v in (decl.get("values") or {}).items()}.get(str(value))
        if isinstance(m, dict) and m.get("layout"):
            out[knob] = str(m["layout"])
    return out


def for_run(project: Path, scenario: Path, parameters: dict, world_knobs: dict, map_name,
            distribution: bool = False) -> list:
    """The layouts a run adds: [{knob, layout, file, sha256, props: place's}], in knob order.
    LayoutError, by name: a layout on a distribution (SSv2 draws its own), a layout no place
    has, a layout wrong for the world, or one prop in two bound layouts (two writers)."""
    from scensim import anchors as anchorsmod  # noqa: PLC0415
    named = bound(scenario, parameters, world_knobs)
    if not named:
        return []
    if distribution:
        raise LayoutError(f"{Path(scenario).name}: knob {next(iter(named))} names a layout, "
                          "which SSv2's own distribution cannot add per run: draw it with a "
                          "suite's sample: instead")
    if not map_name:
        raise LayoutError(f"{Path(scenario).name}: a layout needs the scenario's project map")
    anchors = anchorsmod.for_map(project, map_name)
    out, owner = [], {}
    for knob in sorted(named):
        path = find(project, map_name, named[knob])
        data = Path(path).read_bytes()
        props = place(read(path), anchors, where=f"layout {named[knob]}")
        for p in props:
            if p["name"] in owner:
                raise LayoutError(f"prop {p['name']}: in layout {owner[p['name']]} and layout "
                                  f"{named[knob]}: two writers")
            owner[p["name"]] = named[knob]
        out.append({"knob": knob, "layout": named[knob], "file": str(path),
                    "sha256": sha256(data), "props": props})
    return out


def keep_source(source: Path, run_dir: Path) -> dict:
    """The source's bytes unchanged at <run_dir>/scenario.xosc (issue 189: every run keeps
    the scenario it ran): resolved.yaml's `copy` ({path, sha256, layouts: []}), its sha256
    the source's."""
    data = Path(source).read_bytes()
    out = Path(run_dir) / COPY
    out.write_bytes(data)
    return {"path": str(out), "sha256": sha256(data), "layouts": []}


def write_copy(source: Path, layouts: list, run_dir: Path, zones=()) -> dict:
    """The run's copy of `source` with every layout's props and every knob's zones
    (scensim.zones.for_run's), at <run_dir>/scenario.xosc: resolved.yaml's `copy` ({path,
    sha256, layouts[, zones]})."""
    from scensim import zones as zonesmod  # noqa: PLC0415
    data = inject(source, [p for lay in layouts for p in lay["props"]],
                  zonesmod.properties(list(zones)))
    out = Path(run_dir) / COPY
    out.write_bytes(data)
    copy = {"path": str(out), "sha256": sha256(data),
            "layouts": [{"knob": x["knob"], "layout": x["layout"], "sha256": x["sha256"]}
                        for x in layouts]}
    if zones:
        copy["zones"] = [{"knob": z["knob"], "value": z["value"],
                          "surface_map": z["surface_map"], "properties": z["properties"]}
                         for z in zones]
    return copy
