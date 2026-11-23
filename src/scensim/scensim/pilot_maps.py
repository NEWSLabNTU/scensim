"""The pilot's map variants (roadmap 092 K9, scenario-description.md CS3): the map a pilot loads,
kept apart from the world's own map.

A world declares, beside its knobs and anchors, which maps a pilot may load on each of its maps:

    world:
      pilot_maps:
        Town01:
          current: Town01                                # the world's own map: no variant
          before_works: Town01_before_works              # a project map (assets/maps/<map>)
          edited: {map: Town01_edited, pointcloud: edited}

A scenario binds the variant by a FileHeader property, as knobs and anchors are bound:
``<Property name="scensim.pilot_map" value="$pilot_map"/>`` (a declared parameter) or a variant
by name. ``scensim run`` resolves it before the run: the world loads the scenario's map, the
stack's pilots start on the variant's (a switch request's ``pilot_map``), and ``result.json``
records ``maps: {world, pilot, variant}``. A world map with no entry has the one variant
``current``, itself.

A variant is checked against the world's map by ``testbench check`` (``file_problems``): the
same projection (``map_projector_info.yaml``), so the pilot localises in the world's frame, and
the same point cloud, byte for byte, unless the variant declares ``pointcloud: edited`` (its own
point cloud, an edit of the world's: NDT localises on it). Its lanelets may differ: that is the
point of a variant.
"""
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

KEY = "pilot_maps"
BIND = "scensim.pilot_map"
CURRENT = "current"
PROJECTOR = "map_projector_info.yaml"
EDITED = "edited"


class PilotMapError(ValueError):
    pass


def entry(v):
    """``(map, pointcloud_edited)`` of one variant's declaration, or None when malformed."""
    if isinstance(v, str) and v.strip():
        return v.strip(), False
    if isinstance(v, dict) and set(v) <= {"map", "pointcloud"} and isinstance(v.get("map"), str) \
            and v["map"].strip() and v.get("pointcloud", "same") in ("same", EDITED):
        return v["map"].strip(), v.get("pointcloud") == EDITED
    return None


def problems(decl, where=f"world.{KEY}") -> list:
    """``(where, message)`` for the declaration's shape."""
    if not isinstance(decl, dict):
        return [(where, "is not a mapping: {<world map>: {<variant>: <map>}}")]
    out = []
    for world_map, variants in decl.items():
        w = f"{where}.{world_map}"
        if not isinstance(variants, dict) or not variants:
            out.append((w, "is not a mapping: {current: <map>, <variant>: <map>}"))
            continue
        for name, v in variants.items():
            e = entry(v)
            if e is None:
                out.append((f"{w}.{name}", f"{v!r} is not a project map's name, or "
                            "{map: <map>, pointcloud: edited}"))
            elif name == CURRENT and e != (str(world_map), False):
                out.append((f"{w}.{CURRENT}", f"is the world's own map, {world_map}, not "
                            f"{e[0]}: name the other map as a variant of its own"))
    return out


def variants(decl, world_map) -> dict:
    """``{variant: (map, pointcloud_edited)}`` a pilot may load on ``world_map``."""
    out = {CURRENT: (str(world_map), False)}
    for name, v in ((decl or {}).get(world_map) or {}).items() if isinstance(decl, dict) else ():
        e = entry(v)
        if e is not None:
            out[str(name)] = e
    return out


def binding(path):
    """The scenario's ``scensim.pilot_map`` FileHeader property, or None."""
    root = ET.parse(str(path)).getroot()
    for prop in root.findall("FileHeader/Properties/Property"):
        if prop.get("name") == BIND:
            return (prop.get("value") or "").strip()
    return None


def _declared(path) -> dict:
    root = ET.parse(str(path)).getroot()
    return {p.get("name"): p.get("value")
            for p in root.findall("ParameterDeclarations/ParameterDeclaration")}


def resolve(decl, world_map, path, params=None):
    """``{world, pilot, variant, pointcloud}`` for a scenario at ``path`` on ``world_map`` with
    the run's ``params``, or None when it binds no variant. Refused (PilotMapError) by name: a
    binding to an undeclared parameter, or a variant the world does not declare."""
    text = binding(path)
    if text is None:
        return None
    where = f"{Path(path).name}: {BIND}"
    if text.startswith("$"):
        name = text[1:]
        declared = _declared(path)
        if name not in declared:
            raise PilotMapError(f"{where} = {text}: {name} is not a declared parameter")
        value = (params or {}).get(name, declared[name])
        what = f"{name} = {value!r}"
    else:
        value, what = text, f"the variant {text!r}"
    known = variants(decl, world_map)
    if value not in known:
        raise PilotMapError(f"{where}: {what} is not a pilot map variant of {world_map} "
                            f"(world.{KEY}.{world_map}: {', '.join(sorted(known))})")
    pilot, edited = known[value]
    return {"world": str(world_map), "pilot": pilot, "variant": str(value),
            "pointcloud": EDITED if edited else "same"}


def scenario_problems(decl, world_map, path) -> list:
    """What ``testbench check`` refuses in a scenario's binding, without a run's values: a
    binding to an undeclared parameter, or a literal or default variant the world lacks."""
    try:
        resolve(decl, world_map, path)
    except PilotMapError as e:
        return [str(e)]
    return []


def _pointcloud_digest(d: Path):
    files = sorted(p for p in d.rglob("pointcloud_map*") if p.is_file())
    if not files:
        return None
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(d).as_posix().encode() + b"\0")
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def _projector(d: Path):
    p = d / PROJECTOR
    if not p.is_file():
        return None
    try:
        return yaml.safe_load(p.read_text())
    except yaml.YAMLError:
        return p.read_text()


def file_problems(decl, maps_dir: Path) -> list:
    """``(where, message)``: each variant against its world map's files under ``maps_dir``
    (``assets/maps``): fetched, the same projection, and the same point cloud unless declared
    ``pointcloud: edited``. A world map not fetched is the scenario check's to report."""
    out = []
    if not isinstance(decl, dict):
        return out
    for world_map in decl:
        wd = Path(maps_dir) / str(world_map)
        if not wd.is_dir():
            continue
        wproj, wpcd = _projector(wd), None
        for name, (m, edited) in variants(decl, world_map).items():
            if name == CURRENT:
                continue
            where = f"world.{KEY}.{world_map}.{name}"
            d = Path(maps_dir) / m
            if not d.is_dir():
                out.append((where, f"map {m} is not fetched (assets/maps/{m}): a variant is one "
                            "of the project's maps, in its lock"))
                continue
            if _projector(d) != wproj:
                out.append((where, f"{m}'s {PROJECTOR} is not {world_map}'s: the pilot would "
                            "localise in another frame than the world's"))
            if edited:
                continue
            if wpcd is None:
                wpcd = _pointcloud_digest(wd) or ""
            if (_pointcloud_digest(d) or "") != wpcd:
                out.append((where, f"{m}'s point cloud is not {world_map}'s, and the variant does "
                            "not declare it an edit ({map: " + m + ", pointcloud: edited})"))
    return out
