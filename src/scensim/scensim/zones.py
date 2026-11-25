"""Zone-scoped surface knobs (roadmap 092 K9f-a): a knob value that sets named zones of the
scenario's surface map, which the run writes into its own copy of the scenario and judges from
the world's read-back in the truth file.

A static knob value may carry ``zones:`` (scenario-description.md, section 3)::

    world:
      knobs:
        goal_surface:
          values:
            asphalt: {zones: {ice_at_goal: {class: asphalt}}}
            ice: null
          default: ice

Each zone takes ``class`` (a key of the surface class table), ``wetness`` (OpenSCENARIO's
level: dry, moist, wetWithPuddles, lowFlooded, highFlooded) and ``water_depth`` (m, >= 0). The
run writes them as ``scensim.zone.<id>.<field>`` properties into its copy (scensim.layouts, the
one copy writer): into the Init's RoadCondition when the source has one, else into a new Init
EnvironmentAction whose Environment holds only that RoadCondition.

One rule refuses, by name, in ``testbench check`` and the run (``check``): a zone the
scenario's surface map lacks (its ``scensim.surface_map``, else the map's own surfaces.yaml); a
class not in the table; a class on a soil zone; a field the source already sets for that zone
(two writers); zones on CARLA (086 C7's measured limit); zones on SSv2's own distribution.

The judgement (``judge``): the first ``road_condition`` record of the truth read back after a
step (``after_step``); per zone the class and wetness equal, the water depth and mu within
TOLERANCE of what was sent and the class table (mu: the class's mu times its wet factor at the
zone's wetness times the condition's scale, the world's wetness where the zone sets none). A
mismatch, or no such record, is a ``knob_mismatch`` error run.
"""
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

WETNESS = ("dry", "moist", "wetWithPuddles", "lowFlooded", "highFlooded")
FIELDS = ("class", "wetness", "water_depth")
ZONE_ID = re.compile(r"^[a-z0-9_]+$")
PROPERTY = re.compile(r"^scensim\.zone\.([^.]+)\.([^.]+)$")
SURFACE_MAP = "scensim.surface_map"
TOLERANCE = 1e-6
INIT_ROAD = "Storyboard/Init/Actions/GlobalAction/EnvironmentAction/Environment/RoadCondition"
CARLA_LIMIT = ("CARLA 0.9.16 cannot set a zone's ground: its friction trigger sets all four "
               "wheels of a car by its body's overlap and reaches every car of the same "
               "blueprint, and a per-wheel physics apply rebuilds the car's PhysX vehicle (a "
               "0.14-0.15 m/s step; 086 C7, measured); zones run on Isaac")


class ZoneError(ValueError):
    pass


def property_name(zone: str, field: str) -> str:
    return f"scensim.zone.{zone}.{field}"


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def value_problems(zones, where) -> list:
    """A knob value's ``zones:``, checked by its shape alone: (where, message) pairs."""
    if not isinstance(zones, dict) or not zones:
        return [(where, "is {<zone id>: {class?, wetness?, water_depth?}}")]
    out = []
    for zid, z in zones.items():
        w = f"{where}.{zid}"
        if not isinstance(zid, str) or not ZONE_ID.match(zid):
            out.append((w, "a zone id is [a-z0-9_]+ (the surface map's)"))
            continue
        if not isinstance(z, dict) or not z:
            out.append((w, f"sets one or more of {', '.join(FIELDS)}"))
            continue
        for f in sorted(set(z) - set(FIELDS)):
            out.append((f"{w}.{f}", f"a zone has {', '.join(FIELDS)}"))
        if "class" in z and not (isinstance(z["class"], str) and z["class"]):
            out.append((f"{w}.class", "a class of the surface class table, a string"))
        if "wetness" in z and z["wetness"] not in WETNESS:
            out.append((f"{w}.wetness", f"{z['wetness']!r} is not an OpenSCENARIO wetness "
                                        f"(one of {', '.join(WETNESS)})"))
        if "water_depth" in z and not (_num(z["water_depth"]) and math.isfinite(z["water_depth"])
                                       and z["water_depth"] >= 0):
            out.append((f"{w}.water_depth", "m, a number >= 0"))
    return out


# --- the class table and the surface map ---------------------------------------------------


def default_table() -> Path:
    """The surface class table every world server shares (scensim_world_server's): the
    installed module's, else its installed share, else this workspace's source tree."""
    try:
        from scensim_world_server.classes import SURFACE_CLASSES  # noqa: PLC0415
        return Path(SURFACE_CLASSES)
    except ImportError:
        pass
    try:
        from ament_index_python.packages import get_package_share_directory  # noqa: PLC0415
        p = Path(get_package_share_directory("scensim_world_server")) / "config" / \
            "surface_classes.yaml"
        if p.is_file():
            return p
    except Exception:  # noqa: BLE001 -- no ament index, or the package is not installed
        pass
    from scensim import stack as stackmod  # noqa: PLC0415
    ws = stackmod.workspace_root()
    p = (Path(ws) / "src" / "scensim_world_protocol" / "scensim_world_server" /
         "scensim_world_server" / "surface_classes.yaml") if ws else None
    if p is None or not p.is_file():
        raise ZoneError("the surface class table (scensim_world_server's surface_classes.yaml) "
                        "is neither installed nor in this workspace")
    return p


def load_table(path) -> dict:
    """{class: {"mu": float, "wet": (factor per WETNESS level)}}: a missing level takes the next
    drier one's, dry is 1.0 (as the world servers read it)."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as e:
        raise ZoneError(f"class table {path}: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("classes"), dict):
        raise ZoneError(f"class table {path}: no `classes:` mapping")
    out = {}
    for name, c in data["classes"].items():
        if not isinstance(c, dict) or not _num(c.get("mu")):
            continue
        wet_in, wet, last = c.get("wet") or {}, [], 1.0
        for level in WETNESS:
            last = float(wet_in.get(level, last) if level != "dry" else 1.0)
            wet.append(last)
        out[str(name)] = {"mu": float(c["mu"]), "wet": tuple(wet)}
    return out


def init_road_condition(root):
    """The Init's first RoadCondition element, or None."""
    return root.find(INIT_ROAD)


def _param(root, value, parameters):
    """`value`, or the run's or declared value of the `$parameter` it names."""
    if not (isinstance(value, str) and value.startswith("$")):
        return value
    name = value[1:]
    if name in (parameters or {}):
        return str(parameters[name])
    for d in root.iter("ParameterDeclaration"):
        if d.get("name") == name:
            return d.get("value")
    raise ZoneError(f"${name}: no such parameter")


def source_facts(scenario: Path, parameters=None) -> dict:
    """What the source says about its road: {surface_map: name or None, sets: {(zone, field)}
    (every `scensim.zone.<id>.<field>` property in it, Init or Story)}."""
    root = ET.parse(scenario).getroot()
    rc = init_road_condition(root)
    name = None
    if rc is not None:
        for p in rc.iter("Property"):
            if p.get("name") == SURFACE_MAP:
                name = _param(root, p.get("value"), parameters)
    sets = set()
    for p in root.iter("Property"):
        m = PROPERTY.match(p.get("name") or "")
        if m:
            sets.add(m.groups())
    return {"surface_map": name, "sets": sets}


def find_map(project: Path, map_name: str, name=None, settings=None) -> Path:
    """The surface map a scenario runs on: the named map `name` (its `scensim.surface_map`: the
    testbench's ground.<map>.surface_maps, else the map directory's surfaces/<name>.yaml), else
    the map's own (ground.<map>.surfaces, else the map directory's surfaces.yaml)."""
    from scensim import config, ground  # noqa: PLC0415
    if settings is None:
        try:
            settings = config.project_settings(project)
        except config.ConfigError:
            settings = {}
    g = ((settings.get("ground") or {}).get(map_name) or {}) if map_name else {}
    mdir = Path(project) / "assets" / "maps" / str(map_name)
    if name:
        f = (g.get(ground.NAMED) or {}).get(name)
        p = ground.source(project, f) if f else mdir / ground.NAMED_DIR / f"{name}.yaml"
        if not p.is_file():
            raise ZoneError(f"{SURFACE_MAP} {name}: no such map (ground.{map_name}."
                            f"{ground.NAMED}.{name} in testbench.yaml, or {p})")
        return p
    f = g.get("surfaces")
    p = ground.source(project, f) if f else mdir / ground.KINDS["surfaces"]
    if not p.is_file():
        raise ZoneError(f"map {map_name} has no surface map (ground.{map_name}.surfaces in "
                        f"testbench.yaml, or {p}) to hold zones")
    return p


def read_map(path: Path) -> dict:
    """{zones: {id: its mapping}, table: the class table's path}."""
    try:
        doc = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as e:
        raise ZoneError(f"{path}: {e}") from None
    if not isinstance(doc, dict):
        raise ZoneError(f"{path}: not a mapping")
    zones = {str(z["id"]): z for z in (doc.get("zones") or [])
             if isinstance(z, dict) and z.get("id") is not None}
    table = Path(path).parent / doc["classes"] if doc.get("classes") else None
    return {"path": Path(path), "zones": zones, "table": table}


# --- the rule ------------------------------------------------------------------------------


def check(knob, value, zones: dict, surface_map: dict, table: dict, sets=(), where=None) -> list:
    """Why knob `knob`'s value `value`, setting `zones`, cannot run on `surface_map` (read_map's)
    with class table `table` (load_table's) in a source that sets `sets` ({(zone, field)}): the
    messages, empty when it can. One rule for testbench check and the run."""
    out = []
    w = where or f"knob {knob}={value}"
    for zid in sorted(zones):
        fields = zones[zid] or {}
        z = surface_map["zones"].get(zid)
        if z is None:
            have = ", ".join(sorted(surface_map["zones"])) or "none"
            out.append(f"{w}: zone {zid} is not in {surface_map['path']} (zones: {have})")
            continue
        cls = fields.get("class")
        if cls is not None and cls not in table:
            out.append(f"{w}: zone {zid}: class {cls!r} is not in the surface class table "
                       f"({', '.join(sorted(table))})")
        if cls is not None and z.get("soil") not in (None, False):
            out.append(f"{w}: zone {zid}: a class on a soil zone (soil: {z['soil']}); its class "
                       "is its soil's")
        for f in sorted(fields):
            if (zid, f) in set(sets):
                out.append(f"{w}: zone {zid}.{f}: the scenario sets "
                           f"{property_name(zid, f)} too: two writers, drop one")
    return out


def bound(scenario: Path, parameters: dict, world_knobs: dict) -> dict:
    """{knob: {zone: {field: value}}} for the scenario's bound knobs whose value sets zones."""
    from scensim import knobs as knobsmod  # noqa: PLC0415
    out = {}
    for knob, value in knobsmod.bound(scenario, parameters).items():
        decl = (world_knobs or {}).get(knob)
        if not isinstance(decl, dict) or knobsmod.is_profile_knob(decl):
            continue
        m = {str(k): v for k, v in (decl.get("values") or {}).items()}.get(str(value))
        if isinstance(m, dict) and m.get("zones"):
            out[knob] = {"value": str(value), "zones": m["zones"]}
    return out


def for_run(project: Path, scenario: Path, parameters: dict, world_knobs: dict, map_name,
            simulator: str = None, distribution: bool = False, settings=None) -> list:
    """The zones a run sets: [{knob, value, surface_map, zones: {id: {field: value}},
    properties: {name: value}, map: read_map's, table: load_table's}], in knob order. ZoneError, by name, for anything `check`
    refuses, zones on CARLA, on a distribution, or one zone field in two bound knobs."""
    named = bound(scenario, parameters, world_knobs)
    if not named:
        return []
    first = next(iter(sorted(named)))
    if simulator == "carla":
        raise ZoneError(f"knob {first}={named[first]['value']}: zones: {CARLA_LIMIT}")
    if distribution:
        raise ZoneError(f"{Path(scenario).name}: knob {first} sets zones, which SSv2's own "
                        "distribution cannot add per run: draw it with a suite's sample: instead")
    if not map_name:
        raise ZoneError(f"{Path(scenario).name}: zones need the scenario's project map")
    facts = source_facts(Path(scenario), parameters)
    surface_map = read_map(find_map(project, map_name, facts["surface_map"], settings))
    table = load_table(surface_map["table"] or default_table())
    out, owner, problems = [], {}, []
    for knob in sorted(named):
        value, zones = named[knob]["value"], named[knob]["zones"]
        problems += check(knob, value, zones, surface_map, table, facts["sets"])
        props = {}
        for zid in sorted(zones):
            for f in sorted(zones[zid] or {}):
                if (zid, f) in owner:
                    problems.append(f"zone {zid}.{f}: set by knob {owner[(zid, f)]} and knob "
                                    f"{knob}: two writers")
                owner[(zid, f)] = knob
                props[property_name(zid, f)] = _text(zones[zid][f])
        out.append({"knob": knob, "value": value, "surface_map": str(surface_map["path"]),
                    "zones": zones, "properties": props, "map": surface_map, "table": table})
    if problems:
        raise ZoneError("; ".join(problems))
    return out


def _text(v) -> str:
    return repr(float(v)) if _num(v) else str(v)


def properties(zone_runs: list) -> list:
    """[(name, value)]: every zone property of for_run's list, in name order."""
    return sorted((n, v) for z in zone_runs for n, v in z["properties"].items())


def write(root, props: list):
    """Add `props` ([(name, value)]) to the scenario element tree `root`: into the Init's
    RoadCondition, else into a new Init EnvironmentAction whose Environment holds only one."""
    if not props:
        return
    rc = init_road_condition(root)
    if rc is None:
        actions = root.find("Storyboard/Init/Actions")
        if actions is None:
            raise ZoneError("the scenario has no Storyboard/Init/Actions to set zones in")
        ga = ET.Element("GlobalAction")
        env = ET.SubElement(ET.SubElement(ga, "EnvironmentAction"), "Environment",
                            {"name": "scensim_zones"})
        rc = ET.SubElement(env, "RoadCondition", {"frictionScaleFactor": "1.0",
                                                  "wetness": "dry"})
        actions.insert(0, ga)   # GlobalActions come before Private ones
    ps = rc.find("Properties")
    if ps is None:
        ps = ET.SubElement(rc, "Properties")
    for name, value in props:
        ET.SubElement(ps, "Property", {"name": name, "value": value})


# --- the judgement -------------------------------------------------------------------------


def expected(zone_runs: list, scale: float, wetness: str) -> dict:
    """{knob: {zone: {surface_class, wetness, water_depth, mu}}}: what each zone a knob set must
    read back, from the knob's fields, the map's and the class table (for_run's), under a
    condition of friction scale `scale` and world wetness `wetness` (the ones sent)."""
    out = {}
    for z in zone_runs:
        surface_map, table = z["map"], z["table"]
        for zid, fields in z["zones"].items():
            m = surface_map["zones"].get(zid) or {}
            cls = fields.get("class", m.get("class"))
            wet = fields.get("wetness", m.get("wetness")) or wetness
            depth = fields.get("water_depth", m.get("water_depth"))
            depth = float(depth) if _num(depth) else None
            if cls is None:
                c, mu = "", 0.0
            else:
                c, t = str(cls), table[str(cls)]
                mu = t["mu"] * t["wet"][WETNESS.index(wet)] * float(scale)
            out.setdefault(z["knob"], {})[zid] = {"surface_class": c, "wetness": wet,
                                                  "water_depth": depth, "mu": mu}
    return out


def _zone_off(want: dict, got) -> list:
    if got is None:
        return ["not read back"]
    off = [f for f in ("surface_class", "wetness") if getattr(got, f) != want[f]]
    wd, gd = want["water_depth"], got.water_depth
    if (wd is None) != (gd is None) or (wd is not None and abs(wd - gd) > TOLERANCE):
        off.append("water_depth")
    if abs(want["mu"] - got.mu) > TOLERANCE:
        off.append("mu")
    return off


def judge(zone_runs: list, road_conditions: list) -> tuple:
    """``({knob: result.json knobs.<knob>.zones}, why the run is a knob_mismatch or "")``: each
    zone the knobs set, read from the first `road_condition` record read back after a step."""
    rec = next((r for r in road_conditions if r.after_step and r.applied is not None), None)
    blocks = {z["knob"]: {} for z in zone_runs}
    if rec is None:
        for z in zone_runs:
            blocks[z["knob"]] = {zid: {"sent": f, "read": "missing", "ok": False}
                                 for zid, f in z["zones"].items()}
        return blocks, ("knobs: zones: the truth has no road_condition record read back after a "
                        "step, from a world that sets zones")
    props = (rec.sent or {}).get("properties") or {}
    want = expected(zone_runs, rec.sent.get("friction_scale_factor", 1.0),
                    rec.sent.get("wetness") or "dry")
    bad = []
    for z in zone_runs:
        missing = sorted(n for n, v in z["properties"].items() if props.get(n) != v)
        for zid, fields in z["zones"].items():
            got = (rec.applied.get("zones") or {}).get(zid)
            off = _zone_off(want[z["knob"]][zid], got)
            if missing:
                off = ["not sent"] + off
            blocks[z["knob"]][zid] = {
                "sent": fields, "expected": want[z["knob"]][zid],
                "read": (None if got is None else {f: getattr(got, f) for f in (
                    "surface_class", "wetness", "water_depth", "mu")}),
                "frame": rec.frame, "ok": not off, **({"off": off} if off else {})}
            if off:
                bad.append(f"{z['knob']}: zone {zid} {', '.join(off)}")
    return blocks, (f"knobs: zones read back differ from what was sent: {'; '.join(bad)}"
                    if bad else "")
