"""A scenario and N sample records as one batch's tensors (roadmap 092 K2.2; batch-executor.md
section 4): the entity table, each slot's parameters, and each entity's initial pose and speed.

    c = compile_scenario("cs2.xosc", records, world)

The scenario must pass the compilable subset (`scensim_sampler.subset.check`), and the
environment must meet every condition its verdict lists: `provides` names those it meets (for
example "SSv2's default controller", which scensim_batch.npc provides). The map is the world
adapter's (`world.lane_pose(lane_id, s, offset)` -> (x, y, yaw) per slot, `world.route(x, y,
yaw, length)` -> centreline points), so this module reads no map format itself.

Compiled today: Init TeleportActions to WorldPosition, LanePosition, RelativeWorldPosition and
RelativeObjectPosition (relative to an entity already placed); Init SpeedActions to an absolute
target; inline BoundingBoxes, and an entity's from its catalog (a CatalogReference: the
scenario's CatalogLocations directory, `$(env NAME)` from the environment, or `catalogs`
{catalog name: file or directory}; 092 K2.4); parameters as `$name` (each slot's record value,
else the declared default) or literals. Anything else in Init and an expression `${...}` are
refused here by name (K2.3 and later).
"""
import copy
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import torch

from scensim_sampler import subset

PROVIDED = ("SSv2's default controller",)   # the conditions scensim_batch itself meets


class CompileError(ValueError):
    pass


@dataclass
class Entity:
    name: str
    role: str          # "ego", "default" (SSv2's default behaviour), "prop", "model" (a
                       # behaviour model, 092 K10: `model` names it)
    kind: str          # "vehicle", "pedestrian", "misc"
    length: float
    width: float
    height: float
    cx: float = 0.0    # the box's centre in the entity's frame (BoundingBox/Center)
    cy: float = 0.0
    model: dict = None  # a model entity's {"entry": "scensim.behaviour:<name>", "params": [N
                        # dicts], "anchors": [N dicts], "seeds": [N]}, per slot


@dataclass
class Compiled:
    scenario: str
    n: int
    entities: list
    params: dict                     # name -> [N] tensor (numeric) or list of N (string)
    x: torch.Tensor                  # [N, E] initial pose and speed
    y: torch.Tensor
    yaw: torch.Tensor
    speed: torch.Tensor
    placed: torch.Tensor             # [N, E] bool: Init placed it
    speed_set: torch.Tensor = None   # [N, E] bool: an Init SpeedAction set its speed
    verdict: object = None
    seeds: list = field(default_factory=list)
    storyboard: object = None        # storyboard.Storyboard (K2.3)
    goal_waypoints: list = None      # the ego's Init routing: [(x, y, yaw) [N]], the route goal
    records: list = field(default_factory=list)

    def index(self, name):
        return [e.name for e in self.entities].index(name)

    def of_role(self, role):
        return [i for i, e in enumerate(self.entities) if e.role == role]


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


class _Reads:
    """Which parameters the storyboard's compile reads, and how (094 P4). A read inside a live
    frame (a `floats` called by the compiler itself, or a position the compiler resolves) made
    tensors the storyboard keeps as they are: their recompute is registered, and a reset writes
    the slot's new values into them (Storyboard.rebind). Any other read was baked into the
    compiled structure (a lane name, an execution count, a parameter condition): fixed, and a
    start pool refuses to draw it per episode."""

    def __init__(self):
        self.frames = []           # [(kind, names)]: the open frames, innermost last
        self.fixed = set()
        self.live = set()
        self.entries = []          # [(recompute(P) -> tuple of tensors, the tensors)]

    def read(self, name):
        if self.frames:
            self.frames[-1][1].add(name)
        else:
            self.fixed.add(name)

    def frame(self, kind, fn, recompute=None):
        """fn() inside a frame; a live frame that read a parameter registers its outputs."""
        self.frames.append((kind, set()))
        try:
            out = fn()
        finally:
            _, names = self.frames.pop()
        if names:
            if self.frames:                       # nested: the outer frame owns the reads
                self.frames[-1][1].update(names)
            elif kind == "fixed":
                self.fixed.update(names)
            else:
                outs = out if isinstance(out, tuple) else (out,)
                if not all(isinstance(o, torch.Tensor) for o in outs if o is not None):
                    self.fixed.update(names)      # not tensors: baked
                else:
                    self.live.update(names)
                    self.entries.append((recompute, outs))
        return out


class _Params:
    def __init__(self, declared, records):
        self.declared, self.records = declared, records
        self.n = len(records)
        self.cache = {}
        self.reads = None          # a _Reads while the storyboard compiles

    def value(self, text, where):
        """An attribute: a literal, or `$name` per slot. Returns a list of N."""
        if text is None:
            raise CompileError(f"{where}: missing")
        text = text.strip()
        if text.startswith("${"):
            raise CompileError(f"{where}: expression {text!r} (not compiled yet)")
        if text.startswith("-$"):          # a negated parameter, as SSv2 reads it (CS2's -$decel)
            vals = self.value(text[1:], where)
            nums = [_number(v) for v in vals]
            if any(v is None for v in nums):
                raise CompileError(f"{where}: {text!r} negates a parameter that is not a number")
            return [repr(-v) for v in nums]
        if text.startswith("$"):
            name = text[1:]
            if self.reads is not None:
                self.reads.read(name)
            if name in self.cache:
                return self.cache[name]
            if name not in self.declared:
                raise CompileError(f"{where}: parameter {name!r} is not declared")
            ptype, default = self.declared[name]
            out = []
            for r in self.records:
                v = (r.get("values") or {}).get(name, default)
                out.append(v)
            self.cache[name] = out
            return out
        return [text] * self.n

    def floats(self, text, where):
        if self.reads is not None and not self.reads.frames:
            # called by the storyboard's compiler itself: its tensor is kept as it is
            return self.reads.frame("live", lambda: self._floats(text, where),
                                    recompute=lambda P: (P._floats(text, where),))
        return self._floats(text, where)

    def _floats(self, text, where):
        vals = self.value(text, where)
        out = [_number(v) for v in vals]
        if any(v is None for v in out):
            raise CompileError(f"{where}: {text!r} is not a number in every slot")
        return torch.tensor(out, dtype=torch.float64)


CATALOG_KINDS = ("Vehicle", "Pedestrian", "MiscObject")
_ENV = re.compile(r"\$\(env ([A-Za-z_][A-Za-z0-9_]*)\)")


def _catalog_dirs(root, spath, catalogs):
    """{catalog kind (VehicleCatalog, ...): directory} of the scenario's CatalogLocations,
    `$(env NAME)` substituted, relative paths from the scenario's directory."""
    out = {}
    for loc in root.findall("CatalogLocations/*"):
        d = loc.find("Directory")
        if d is None or not d.get("path"):
            continue
        raw = d.get("path")
        missing = [m for m in _ENV.findall(raw) if m not in os.environ]
        if missing:
            out[loc.tag] = (None, f"{raw}: {', '.join(missing)} not in the environment")
            continue
        path = Path(_ENV.sub(lambda m: os.environ[m.group(1)], raw))
        out[loc.tag] = (path if path.is_absolute() else Path(spath).parent / path, None)
    return out


def _catalog_entry(ref, where, dirs, catalogs, cache):
    """The catalog's element (Vehicle, Pedestrian or MiscObject) a CatalogReference names."""
    name, entry = ref.get("catalogName"), ref.get("entryName")
    places = []
    if catalogs and name in catalogs:
        places.append(Path(catalogs[name]))
    places += [d for d, _ in dirs.values() if d is not None]
    for place in places:
        files = sorted(place.glob("*.xosc")) if place.is_dir() else [place]
        for f in files:
            if f not in cache:
                try:
                    cache[f] = ET.parse(f).getroot()
                except (ET.ParseError, OSError):
                    cache[f] = None
            croot = cache[f]
            if croot is None:
                continue
            for cat in croot.iter("Catalog"):
                if cat.get("name") != name:
                    continue
                for el in cat:
                    if el.tag in CATALOG_KINDS and el.get("name") == entry:
                        return el
    why = "; ".join(w for _, w in dirs.values() if w)
    raise CompileError(f"{where}: catalog {name!r} has no {entry!r} in "
                       f"{', '.join(map(str, places)) or 'no catalog location'}"
                       + (f" ({why})" if why else ""))


def _resolved(obj, where, dirs, catalogs, cache):
    """The ScenarioObject with its CatalogReference replaced by the entry it names. A
    parameterised bounding box is refused (the catalog's parameters are not compiled)."""
    ref = obj.find("CatalogReference")
    if ref is None:
        return obj
    el = copy.deepcopy(_catalog_entry(ref, where, dirs, catalogs, cache))
    for node in el.iter("BoundingBox"):
        for sub in node.iter():
            bad = [k for k, v in sub.attrib.items() if v.strip().startswith("$")]
            if bad:
                raise CompileError(f"{where}: catalog entry {el.get('name')!r}'s BoundingBox "
                                   f"{sub.tag}@{bad[0]} is a parameter (not compiled)")
    out = copy.copy(obj)
    out[:] = [el if c is ref else c for c in obj]
    return out


def _box(obj, where):
    dims = obj.find(".//BoundingBox/Dimensions")
    if dims is None:
        raise CompileError(f"{where}: no BoundingBox")
    centre = obj.find(".//BoundingBox/Center")
    cx, cy = ((float(centre.get("x", 0)), float(centre.get("y", 0))) if centre is not None
              else (0.0, 0.0))
    return tuple(float(dims.get(k)) for k in ("length", "width", "height")) + (cx, cy)


def _kind(obj):
    for tag, kind in (("Vehicle", "vehicle"), ("Pedestrian", "pedestrian"),
                      ("MiscObject", "misc")):
        if obj.find(tag) is not None:
            return kind
    return None


MODEL_PREFIX = "scensim.behaviour:"
ANCHOR = "anchor."      # a model's property of the crossing's geometry, not one of its params


def _models_provided():
    """The behaviour models scensim_batch runs batched: each one whose class declares torch."""
    try:
        from scensim import behaviour
    except ImportError:
        return []
    return [f"behaviour model {MODEL_PREFIX}{name}" for name, cls in behaviour.MODELS.items()
            if "torch" in getattr(cls, "array_api", ())]


def _model_of(obj):
    """The behaviour model an entity's ObjectController names, or None."""
    for c in obj.iter("Controller"):
        for prop in c.iter("Property"):
            if prop.get("name") == "model" and (prop.get("value") or "").startswith(MODEL_PREFIX):
                return prop.get("value")
    return None


def _model_spec(obj, name, where, P, records):
    """A model entity's entry point, its parameters and anchors per slot (each property's
    value resolved as any attribute: a literal or `$name`), and its seed per slot (the
    record's `seeds.pilots.<entity>`, else the scenario's)."""
    from scensim import behaviour
    entry = _model_of(obj)
    model = entry[len(MODEL_PREFIX):]
    if model not in behaviour.MODELS:
        raise CompileError(f"{where}: behaviour model {entry!r} unknown (known: "
                           f"{', '.join(MODEL_PREFIX + m for m in behaviour.MODELS)})")
    n = P.n
    params, anchors = [dict() for _ in range(n)], [dict() for _ in range(n)]
    for c in obj.iter("Controller"):
        for prop in c.iter("Property"):
            key = prop.get("name")
            if key == "model":
                continue
            vals = P.value(prop.get("value"), f"{where}/.../Property[@name='{key}']")
            for i in range(n):
                if key.startswith(ANCHOR):
                    anchors[i][key[len(ANCHOR):]] = _number(vals[i])
                else:
                    params[i][key] = vals[i]
    cls = behaviour.MODELS[model]
    for i in range(n):
        try:
            params[i] = behaviour.walker.resolve(params[i]) if cls is behaviour.walker.GapAcceptanceWalker \
                else params[i]
        except ValueError as e:
            raise CompileError(f"{where}: slot {i}: {e}") from None
    seeds = []
    for i, r in enumerate(records):
        sd = r.get("seeds") or {}
        s = (sd.get("pilots") or {}).get(name, sd.get("scenario"))
        if s is None:
            raise CompileError(f"{where}: slot {i}: no seed for {name!r} (seeds.pilots.{name} "
                               "or seeds.scenario)")
        seeds.append(int(s))
    return {"entry": entry, "model": model, "params": params, "anchors": anchors,
            "seeds": seeds}


def compile_scenario(path, records, world, provides=(), device="cpu", catalogs=None):
    """The batch for `records` (N sample records, slot i = records[i]) of scenario `path`.
    `catalogs`: {catalog name: file or directory}, searched before the scenario's
    CatalogLocations."""
    if not records:
        raise CompileError(f"{path}: no records (a batch of no slots)")
    v = subset.check(path)
    if not v.compiles:
        raise CompileError(f"{path}: {v.line()}")
    met = set(PROVIDED) | set(provides) | set(_models_provided())
    # a condition is "<what>: <reason>"; a behaviour model's <what> has a colon of its own
    # (scensim.behaviour:<name>), so a condition is met by the <what> it starts with
    unmet = [c for c in v.conditions if not any(c.startswith(m + ": ") for m in met)]
    if unmet:
        raise CompileError(f"{path}: compiles only if: {'; '.join(unmet)}; this environment "
                           f"provides {', '.join(sorted(met))}")
    root, spath = subset.read(path)
    from scensim_sampler.xosc import Scenario
    declared = Scenario(spath).parameters
    P = _Params(declared, records)
    n = len(records)

    entities = []
    dirs, cache = _catalog_dirs(root, spath, catalogs), {}
    for obj in root.findall("Entities/ScenarioObject"):
        name = obj.get("name")
        where = f"Entities/ScenarioObject[@name='{name}']"
        obj = _resolved(obj, where, dirs, catalogs, cache)
        kind = _kind(obj)
        if kind is None:
            raise CompileError(f"{where}: neither Vehicle, Pedestrian nor MiscObject")
        length, width, height, cx, cy = _box(obj, where)
        if name in v.egos:
            role = "ego"
        elif kind == "misc":
            role = "prop"
        elif _model_of(obj) is not None:
            role = "model"         # a behaviour model drives it (092 K10)
        elif kind == "vehicle" and all(not c.findall(".//Property")
                                        for c in obj.iter("Controller")):
            # no controller, or one that sets nothing (an empty Properties): SSv2's default
            # vehicle behaviour, as its interpreter gives such an entity (092 K2.4)
            role = "default"
        else:
            raise CompileError(f"{where}: a {kind} with a controller or behaviour model "
                               "(not compiled yet)")
        ent = Entity(name, role, kind, length, width, height, cx, cy)
        if role == "model":
            ent.model = _model_spec(obj, name, where, P, records)
        entities.append(ent)
    names = [e.name for e in entities]
    e = len(entities)
    z = torch.zeros(n, e, dtype=torch.float64)
    x, y, yaw, speed = z.clone(), z.clone(), z.clone(), z.clone()
    placed = torch.zeros(n, e, dtype=torch.bool)
    speed_set = torch.zeros(n, e, dtype=torch.bool)
    goal = None

    for pr in root.findall("Storyboard/Init/Actions/Private"):
        ref = pr.get("entityRef")
        if ref not in names:
            raise CompileError(f"Init/Private[@entityRef='{ref}']: no such entity")
        i = names.index(ref)
        for k, pa in enumerate(pr.findall("PrivateAction")):
            where = f"Storyboard/Init/Actions/Private[@entityRef='{ref}']/PrivateAction[{k + 1}]"
            pos = pa.find("TeleportAction/Position")
            sp = pa.find("LongitudinalAction/SpeedAction/SpeedActionTarget/AbsoluteTargetSpeed")
            if entities[i].role == "model" and pos is None:
                _model_init_action(pa, sp, where, ref)
            if pos is not None:
                px, py, pyaw = _position(pos, where, P, world, names, x, y, yaw, placed)
                x[:, i], y[:, i], yaw[:, i] = px, py, pyaw
                placed[:, i] = True
            elif sp is not None:
                speed[:, i] = P.floats(sp.get("value"), where + "/.../AbsoluteTargetSpeed")
                speed_set[:, i] = True
            elif pa.find("ControllerAction") is not None:
                continue   # the ego's pilot: the batch's policy (subset.check said so)
            elif pa.find("RoutingAction") is not None:
                from . import storyboard as sbmod
                ra = next(iter(pa.find("RoutingAction")))
                if ra.tag not in sbmod.EGO_GOAL or entities[i].role != "ego":
                    raise CompileError(f"{where}: RoutingAction/{ra.tag} on {ref!r} (batch "
                                       "executor pending)")
                # the policy's task: the slot's route goal (Init positions may be relative)
                try:
                    goal = sbmod.routing_waypoints(
                        ra, f"{where}/RoutingAction/{ra.tag}",
                        lambda p_, w_: _position(p_, w_, P, world, names, x, y, yaw, placed))
                except sbmod.StoryboardError as err:
                    raise CompileError(str(err)) from None
            else:
                tag = next(iter(pa), None)
                raise CompileError(f"{where}: {getattr(tag, 'tag', 'empty')} in Init "
                                   "(not compiled yet)")
    params = {}
    for name, (ptype, _) in declared.items():
        vals = P.value("$" + name, f"ParameterDeclaration {name}")
        nums = [_number(t) for t in vals]
        params[name] = (torch.tensor(nums, dtype=torch.float64)
                        if ptype in ("double", "int", "unsignedInt", "unsignedShort")
                        and all(t is not None for t in nums) else list(vals))
    seeds = [(r.get("seeds") or {}).get("scenario") for r in records]
    from . import storyboard as sbmod
    info = _StoryInfo(n, P, entities, world, names, x, y, yaw, placed)
    sb_el = root.find("Storyboard")
    try:
        story = sbmod.compile_storyboard(sb_el, info) if sb_el is not None else None
    except sbmod.StoryboardError as e:
        raise CompileError(str(e)) from None
    to = (lambda t: t.to(device))
    return Compiled(str(spath), n, entities, params, to(x), to(y), to(yaw), to(speed),
                    placed.to(device), speed_set.to(device), v, seeds, storyboard=story,
                    records=list(records), goal_waypoints=goal)


def _model_init_action(pa, sp, where, ref):
    """Issue 175: in Init a model entity takes a TeleportAction (its placement) and, in the
    batch only, a step AbsoluteTargetSpeed (its speed at reset); anything else is refused by
    name, since only its model moves it. Seats refuse the speed too."""
    dyn = pa.find("LongitudinalAction/SpeedAction/SpeedActionDynamics")
    if sp is not None and dyn is not None and dyn.get("dynamicsShape") == "step":
        return
    first = next(iter(pa), None)
    inner = next(iter(first), None) if first is not None else None
    what = "/".join(x.tag for x in (first, inner) if x is not None) or "an empty PrivateAction"
    if sp is not None:
        what += f" with dynamicsShape {dyn.get('dynamicsShape') if dyn is not None else None!r}"
    raise CompileError(f"{where}: {what} on {ref!r}, a model entity: only its model moves it; "
                       "in Init it takes a TeleportAction and a step AbsoluteTargetSpeed "
                       "(issue 175)")


class _StoryInfo:
    """What the storyboard's compile reads: the slots, parameters, entities, map."""

    def __init__(self, n, P, entities, world, names, x, y, yaw, placed):
        self.n, self.P, self.entities, self.world = n, P, entities, world
        self.names, self.x, self.y, self.yaw, self.placed = names, x, y, yaw, placed
        self.defaults = [i for i, e in enumerate(entities) if e.role == "default"]

    def index(self, name, where):
        if name not in self.names:
            raise CompileError(f"{where}: no entity {name!r}")
        return self.names.index(name)

    def position(self, pos, where):
        return self.position_with(self.P, pos, where)

    def position_with(self, P, pos, where):
        """position() with another slot set's parameters (a reset's records, Storyboard.rebind)."""
        if pos is None:
            raise CompileError(f"{where}: missing")
        return _position(pos, where, P, self.world, self.names, self.x, self.y, self.yaw,
                         self.placed)


def _position(pos, where, P, world, names, x, y, yaw, placed):
    w = pos.find("WorldPosition")
    if w is not None:
        h = w.get("h")
        return (P.floats(w.get("x"), where + "/WorldPosition@x"),
                P.floats(w.get("y"), where + "/WorldPosition@y"),
                P.floats(h, where + "/WorldPosition@h") if h is not None
                else torch.zeros(P.n, dtype=torch.float64))
    lp = pos.find("LanePosition")
    if lp is not None:
        lanes = P.value(lp.get("laneId"), where + "/LanePosition@laneId")
        s = P.floats(lp.get("s"), where + "/LanePosition@s")
        off = P.floats(lp.get("offset") or "0", where + "/LanePosition@offset")
        px, py, pyaw = world.lane_pose(lanes, s, off)
        pyaw = torch.as_tensor(pyaw, dtype=torch.float64)
        ori = lp.find("Orientation")
        if ori is not None and ori.get("h") is not None:   # the standard's: relative to the lane
            h = P.floats(ori.get("h"), where + "/LanePosition/Orientation@h")
            kind = ori.get("type", "relative")
            if kind not in ("relative", "absolute"):
                raise CompileError(f"{where}/LanePosition/Orientation@type: {kind!r}")
            pyaw = pyaw + h if kind == "relative" else h
        return (torch.as_tensor(px, dtype=torch.float64), torch.as_tensor(py, dtype=torch.float64),
                pyaw)
    for tag in ("RelativeWorldPosition", "RelativeObjectPosition"):
        rp = pos.find(tag)
        if rp is not None:
            ref = rp.get("entityRef")
            if ref not in names or not bool(placed[:, names.index(ref)].all()):
                raise CompileError(f"{where}/{tag}: entity {ref!r} is not placed before it")
            j = names.index(ref)
            dx = P.floats(rp.get("dx"), f"{where}/{tag}@dx")
            dy = P.floats(rp.get("dy"), f"{where}/{tag}@dy")
            if tag == "RelativeObjectPosition":   # in the reference's own frame
                c, s_ = torch.cos(yaw[:, j]), torch.sin(yaw[:, j])
                dx, dy = c * dx - s_ * dy, s_ * dx + c * dy
            return x[:, j] + dx, y[:, j] + dy, yaw[:, j].clone()
    tag = next(iter(pos), None)
    raise CompileError(f"{where}: {getattr(tag, 'tag', 'empty')} (not compiled yet)")


__all__ = ["CompileError", "Compiled", "Entity", "PROVIDED", "compile_scenario"]
_ = math
