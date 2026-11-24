"""World knobs per run (093 D7 gap 1; scenario-description.md section 3): a scenario's bound
knobs (FileHeader `scensim.knob.<knob> = param:<parameter>`) take their run's parameter values,
which go to the world before the scenario starts; the world's answer is read back and
`result.json` records it under `knobs`. A run whose applied values differ from its record's is
an error run, excluded from rates.

What a knob's value means is the world's: `knobs:` under the world in testbench.yaml (a subset
of section 3's world.yaml, which may carry it later)::

    world:
      knobs:
        illumination:
          values:
            day:   {weather: {sun_altitude_angle: 60}}
            night: {weather: {sun_altitude_angle: -30, street_lights: 100}}
          default: day
        surface:
          values:
            dry:      {surface_map: dry, mu: 1.0}
            wet:      {surface_map: wet, mu: 0.7}
            wet_look: {weather: {wetness: 80}, physics: none}   # visual only

A knob with ``profile: true`` (092 K9) changes over the run instead: a number in ``range``,
setting one scenario-environment field (``sets``), bound in the scenario to a profile along
time or a lane anchor (scensim_sampler.profiles)::

        visibility: {profile: true, sets: fog_visual_range, range: [50, 1000], default: 1000}

The bridge applies it each frame (``~/set_knob_profiles``), sending a value when it has moved
by ``step`` (default 1 % of the range) since the last, and the gap trace records each frame's
commanded value and the world's read-back; ``result.json``'s knobs ``profiles`` summarises them,
and a read-back off by more than the field's tolerance is an error run.

A value maps to weather parameters (the world server's names, through the bridge's
set_weather) and/or a named surface map (Isaac: the scenario's RoadCondition
`scensim.surface_map`, linked by the project's ground). Every run sends the testbench's
weather baseline merged with its knobs' parameters, so no run inherits another's weather.

A value may instead set the scenario environment by field, `environment: {sun_elevation: 1.0472}`
(radians, as OpenSCENARIO's angles; each field's range is FIELD_RANGES)
(092 K9e; the fields a profile sets): the portable form, which both world servers apply and
read back. The run sends it as a profile held constant from time 0 (`<knob>.<field>`), judged on
every frame's read-back after the send. One value sets a quantity in one form (SAME_QUANTITY).

On Isaac there is no weather service: a value with weather parameters is refused there by name
(its scenario's EnvironmentAction sets the sky). On CARLA a surface map cannot be applied, and weather (wetness) is visual only: a value that
names a surface map or a friction (`mu`) is refused there by name, unless it says
`physics: none`, and then the record says the friction was not applied.
"""
import math
from pathlib import Path

KINDS = ("weather", "environment", "surface_map", "mu", "physics")
TOLERANCE = 1e-3   # a read-back may round (the world server stores floats)


class KnobError(ValueError):
    pass


# a profile knob's fields, and the simulators whose world servers apply and read each back
PROFILE_FIELDS = {
    "fog_visual_range": ("carla", "isaac"),
    "sun_elevation": ("carla", "isaac"),
    "sun_azimuth": ("carla", "isaac"),
    "precipitation_intensity": ("carla", "isaac"),
    "cloud_cover_oktas": ("carla",),     # Isaac has no cloud state to read back
}
# the scenario's EnvironmentAction elements that set the same part (two writers are refused)
PROFILE_ELEMENTS = {"fog_visual_range": ("Fog",), "sun_elevation": ("Sun", "TimeOfDay"),
                    "sun_azimuth": ("Sun", "TimeOfDay"), "precipitation_intensity":
                    ("Precipitation",), "cloud_cover_oktas": ("Weather",)}
# a static value's `environment:` field (092 K9e) and the CARLA weather parameters that are the
# same quantity: one value sets a quantity in one form
SAME_QUANTITY = {"sun_elevation": ("sun_altitude_angle",), "sun_azimuth": ("sun_azimuth_angle",),
                 "fog_visual_range": ("fog_density", "fog_distance"),
                 "precipitation_intensity": ("precipitation",),
                 "cloud_cover_oktas": ("cloudiness",)}
# each environment field's unit and range (092 K9e): a value, or a profile knob's range, outside
# it is refused, naming the unit (an angle also its value read as degrees, in radians)
FIELD_RANGES = {
    "sun_elevation": (lambda v: -math.pi / 2 <= v <= math.pi / 2, "[-1.5708, 1.5708] rad", True),
    "sun_azimuth": (lambda v: 0.0 <= v < 2 * math.pi, "[0, 6.2832) rad", True),
    "fog_visual_range": (lambda v: v > 0.0, "above 0 m", False),
    "precipitation_intensity": (lambda v: v >= 0.0, "0 or more mm/h", False),
    "cloud_cover_oktas": (lambda v: 0.0 <= v <= 8.0, "[0, 8] oktas", False),
}


def field_range_problem(field: str, v: float):
    """Why `v` is no value of environment field `field`, or None."""
    rule = FIELD_RANGES.get(field)
    if rule is None or rule[0](float(v)):
        return None
    ok, text, angle = rule
    conv = f" ({float(v):g} deg is {math.radians(float(v)):.4f} rad)" if angle else ""
    return f"{float(v):g} is outside {field}'s range {text}{conv}"


PROFILE_KEYS = ("profile", "sets", "range", "default", "step", "min_interval")
# s of scenario time between two sends of a profile, unless declared: a SetEnvironment costs
# the frame it is sent in (CARLA, Town01 with 20 NPCs, 2026-11-22: frame p95 4-7 ms without a
# profile, 21-222 ms with one sent every frame)
PROFILE_MIN_INTERVAL = 1.0
# the share of a ramp's end value the world may trail it by before `check` warns
PROFILE_LAG_SHARE = 0.25
SET_KNOB_PROFILES = "/scenario_world_bridge/set_knob_profiles"


def is_profile_knob(decl) -> bool:
    return isinstance(decl, dict) and decl.get("profile") is True


def profile_tolerance(decl) -> float:
    """How far a read-back may be from the value sent: an okta is whole, the rest float."""
    if decl.get("sets") == "cloud_cover_oktas":
        return 0.5
    lo, hi = decl["range"]
    return 1e-3 + 1e-4 * (hi - lo)


def bound_profiles(scenario: Path, parameters: dict) -> dict:
    """{knob: (coordinate, lane, [(x, value)])}: each profile-bound knob, its breakpoints with
    the run's values (or the declared defaults) in place of its $parameters."""
    from scensim_sampler import profiles as P
    from scensim_sampler.xosc import Scenario
    sc = Scenario(scenario)
    vals = {k: v for k, (_t, v) in sc.parameters.items()}
    vals.update(parameters or {})
    out = {}
    for knob, (coord, lane, points) in sc.knob_profiles.items():
        try:
            out[knob] = (coord, lane, P.evaluate(points, vals, f"scensim.knob.{knob}"))
        except P.ProfileError as e:
            raise KnobError(str(e)) from None
    return out


def lag_notes(world_knobs: dict, profiles: dict, speeds=None) -> list:
    """Warnings for ramps the world will trail by more than PROFILE_LAG_SHARE of their end
    value. The bridge sends at most once per min_interval, and a world may show a send a tick
    late, so the world trails a ramp by about 2 x min_interval x its rate (fog ramping 15.8 m/s
    trails by ~31 m at 1 s, which matters near 50 m). A `time` ramp's rate is per second; an
    `s(<lane>)` ramp's is per metre times the lane's speed (`speeds`: {lane: m/s}, its speed
    limit), and without one it is not judged. Each warning names the interval that would fit."""
    out = []
    for knob, (coord, lane, points) in profiles.items():
        decl = (world_knobs or {}).get(knob) or {}
        if not is_profile_knob(decl):
            continue
        mi = decl.get("min_interval")
        mi = PROFILE_MIN_INTERVAL if mi is None else float(mi)
        speed = 1.0 if coord == "time" else (speeds or {}).get(lane)
        if not speed or mi <= 0:
            continue
        unit = "s" if coord == "time" else "m"
        for (x0, v0), (x1, v1) in zip(points, points[1:]):
            if x1 <= x0 or v1 == v0:
                continue
            rate = abs(v1 - v0) / (x1 - x0) * speed       # per second
            lag = min(2.0 * mi * rate, abs(v1 - v0))
            allowed = PROFILE_LAG_SHARE * abs(v1)
            if lag <= allowed:
                continue
            fit = allowed / (2.0 * rate)
            along = "" if coord == "time" else f" at {speed:g} m/s"
            out.append(f"knob {knob}: the world trails its ramp {x0:g} -> {x1:g} {unit} "
                       f"({v0:g} -> {v1:g}{along}) by up to {lag:.3g} (about 2 x min_interval "
                       f"{mi:g} s x {rate:.3g}/s), {100 * lag / abs(v1) if v1 else float('inf'):.0f} % "
                       f"of its end value; min_interval: {fit:.2g} would keep it within "
                       f"{100 * PROFILE_LAG_SHARE:.0f} % (testbench.yaml world.knobs.{knob})")
    return out


def profile_plan(world_knobs: dict, profiles: dict, simulator: str, anchors=None,
                 environment=()) -> list:
    """The bridge's profiles (its `~/set_knob_profiles` JSON's list) for a run's bound
    profiles. KnobError names a knob the world lacks or declares without `profile: true`, a
    field this simulator cannot apply and read back, a value outside the knob's range, a lane
    the world lacks or resolved without its centreline, or a part the scenario's own
    EnvironmentAction also sets (`environment`: knobs.environment_weather's elements)."""
    out = []
    for knob, (coord, lane, points) in profiles.items():
        decl = (world_knobs or {}).get(knob)
        if decl is None:
            raise KnobError(f"knob {knob!r}: the world declares no such knob (testbench.yaml "
                            f"world.knobs: {', '.join(sorted(world_knobs or {})) or 'none'})")
        if not is_profile_knob(decl):
            raise KnobError(f"knob {knob}: bound to a profile, but the world declares it with "
                            "values, not profile: true")
        field = decl["sets"]
        if simulator not in PROFILE_FIELDS[field]:
            raise KnobError(f"knob {knob}: a profile of {field}, which the {simulator} world "
                            f"server cannot apply and read back ("
                            f"{', '.join(PROFILE_FIELDS[field])} only)")
        both = [e for e in PROFILE_ELEMENTS[field] if e in environment]
        if both:
            raise KnobError(f"knob {knob}: a profile of {field}, and the scenario's "
                            f"EnvironmentAction sets {', '.join(both)} too: two writers, drop one")
        lo, hi = decl["range"]
        off = [v for _, v in points if not lo <= v <= hi]
        if off:
            raise KnobError(f"knob {knob}: value {off[0]:g} is outside its range [{lo:g}, {hi:g}]")
        if coord == "time":
            coordinate = "time"
        else:
            a = (anchors or {}).get(lane)
            if not a or a.get("kind") != "lane" or "heading_s" not in a:
                raise KnobError(f"knob {knob}: s({lane}): the world has no resolved lane "
                                f"{lane} (the map's anchors.resolved.json)")
            if "x" not in a or "y" not in a:
                raise KnobError(f"knob {knob}: s({lane}): the map's anchors were resolved "
                                "without the lane's centreline; its author resolves them again")
            coordinate = {"lane": lane, "s": a["heading_s"], "x": a["x"], "y": a["y"]}
        step = decl.get("step") or 0.01 * (hi - lo)
        mi = decl.get("min_interval")
        mi = PROFILE_MIN_INTERVAL if mi is None else float(mi)
        out.append({"knob": knob, "field": field, "step": float(step), "min_interval": mi,
                    "coordinate": coordinate, "points": [[x, v] for x, v in points]})
    return out


def static_tolerance(field: str, value: float) -> float:
    """How far a constant's read-back may be from its value: half an okta, else float."""
    return 0.5 if field == "cloud_cover_oktas" else 1e-3 + 1e-4 * abs(value)


def static_profiles(environment: dict, environment_elements=(), profiles=None) -> list:
    """The bridge's profiles for a run's static `environment:` values (092 K9e;
    `environment`: plan's {knob: {field: value}}): one held constant from time 0 per field,
    named `<knob>.<field>`, so it is sent and read back as a profile is. KnobError names a
    field the scenario's EnvironmentAction or a profile knob (`profiles`, profile_plan's list)
    also sets: two writers."""
    out = []
    taken = {p["field"]: p["knob"] for p in (profiles or [])}
    for knob, fields in (environment or {}).items():
        for f, v in fields.items():
            both = [e for e in PROFILE_ELEMENTS[f] if e in environment_elements]
            if both:
                raise KnobError(f"knob {knob}: environment.{f}, and the scenario's "
                                f"EnvironmentAction sets {', '.join(both)} too: two writers, "
                                "drop one")
            if f in taken:
                raise KnobError(f"knob {knob}: environment.{f}, and profile knob {taken[f]} "
                                f"sets {f} too: two writers, drop one")
            taken[f] = f"{knob}.{f}"
            out.append({"knob": f"{knob}.{f}", "field": f, "step": 1e-3,
                        "min_interval": PROFILE_MIN_INTERVAL, "coordinate": "time",
                        "points": [[0.0, float(v)]], "static": True})
    return out


def _static_summary(p: dict, lines: list) -> dict:
    """A constant's summary: every frame's read-back after its first send within the field's
    tolerance, none missing, at least one."""
    value = p["points"][0][1]
    tol = static_tolerance(p["field"], value)
    sends = [k for k in lines if k.sent]
    after = lines[lines.index(sends[0]) + 1:] if sends else []
    unread = sum(1 for k in after if k.applied is None)
    off = [k.frame for k in after if k.applied is not None and abs(k.applied - value) > tol]
    dev = max((abs(k.applied - value) for k in after if k.applied is not None), default=None)
    read = [k.applied for k in after if k.applied is not None]
    return {"sets": p["field"], "static": True, "value": value, "frames": len(lines),
            "sent": len(sends), "judged": len(after), "unread": unread, "off_frames": off[:20],
            "max_deviation": dev, "tolerance": tol,
            "first_read_back": (sends[0].applied if sends else None),
            "read_back": (read[-1] if read else None),
            "ok": bool(after) and not unread and not off}


def merge_static(block: dict, summary: dict) -> dict:
    """result.json's `knobs` with each static `environment:` field's read-back (profile_summary's
    `<knob>.<field>` entries) in its knob's `applied`, the knob not ok when a field is off."""
    for name, e in summary.items():
        entry = (block.get("knobs") or {}).get(name.split(".", 1)[0])
        if e.get("static") and entry is not None:
            entry.setdefault("applied", {})[e["sets"]] = e["read_back"]
            entry["ok"] = entry.get("ok", True) and e["ok"]
    return block


def profile_summary(world_knobs: dict, plan: list, knob_lines: list) -> dict:
    """result.json knobs' `profiles`, from the gap trace's knob lines: per knob its field,
    coordinate, breakpoints, step and min_interval, frames, sends, the range commanded, and how
    the world's read-backs matched. A read-back taken right after a send may still show the
    send before it (CARLA applies a weather at its next tick): it matches if it equals this
    send's value or the one before, within the field's tolerance (`lagged` counts the second).
    The first send's read-back, which has nothing before it to lag to, is recorded, not judged.
    ok: every later send's read-back matched, and none is missing."""
    out = {}
    for p in plan:
        knob = p["knob"]
        decl = (world_knobs or {}).get(knob) or {}
        lines = [k for k in knob_lines if k.knob == knob]
        if p.get("static"):
            out[knob] = _static_summary(p, lines)
            continue
        sends = [k for k in lines if k.sent]
        tol = profile_tolerance(decl) if decl.get("range") else TOLERANCE
        unread, lagged, off, dev = 0, 0, [], None
        for i, k in enumerate(sends):
            if k.applied is None:
                unread += 1
                continue
            if i == 0:
                continue
            d_now = abs(k.commanded - k.applied)
            d_prev = abs(sends[i - 1].commanded - k.applied)
            d = min(d_now, d_prev)
            dev = d if dev is None else max(dev, d)
            if d_now > tol and d_prev <= tol:
                lagged += 1
            if d > tol:
                off.append(k.frame)
        commanded = [k.commanded for k in lines]
        # how far the world trailed the profile: per frame, the commanded value against the
        # world's last read-back (the step, min_interval and the one-tick lag together)
        trail = [abs(k.commanded - k.applied) for k in lines[1:] if k.applied is not None]
        ok = bool(lines) and not unread and not off
        coord = p["coordinate"]
        out[knob] = {"sets": p["field"],
                     "coordinate": coord if coord == "time" else f"s({coord['lane']})",
                     "points": p["points"], "step": p["step"],
                     "min_interval": p.get("min_interval", 0.0), "frames": len(lines),
                     "sent": len(sends), "unread": unread, "lagged": lagged,
                     "off_frames": off[:20], "max_deviation": dev, "tolerance": tol,
                     "max_lag": (max(trail) if trail else None),
                     # what the profile asked for over the run: a profile that never moved
                     # shows here (its coordinate never advanced)
                     "commanded": ([min(commanded), max(commanded)] if commanded else None),
                     "first_read_back": (sends[0].applied if sends else None),
                     "ok": ok}
    return out


def bound(scenario: Path, parameters: dict) -> dict:
    """{knob: value}: each bound knob's parameter, the run's value or its declared default."""
    from scensim_sampler.xosc import Scenario
    sc = Scenario(scenario)
    out = {}
    for knob, param in sc.knobs.items():
        v = (parameters or {}).get(param, sc.parameters[param][1])
        out[knob] = str(v)
    return out


WEATHER_ELEMENTS = ("Weather", "TimeOfDay", "Sun", "Fog", "Precipitation", "Wind")


def environment_weather(scenario: Path) -> list:
    """The weather a scenario's EnvironmentActions set during the run (the bridge forwards
    Weather and TimeOfDay to the world): the element names found, empty when none."""
    from scensim_sampler.subset import read
    root, _ = read(scenario)
    found = []
    for env in root.iter("EnvironmentAction"):
        for tag in WEATHER_ELEMENTS:
            if env.find(f".//{tag}") is not None and tag not in found:
                found.append(tag)
    return found


def problems(world_knobs: dict, where="world.knobs", simulator: str = None) -> list:
    """The testbench's knob declarations, checked: (where, message) pairs. With the testbench's
    `simulator`, each value is also held to what that simulator's run applies (issue 154)."""
    out = []
    if world_knobs is None:
        return out
    if not isinstance(world_knobs, dict):
        return [(where, "is {knob: {values: {value: {weather?, surface_map?, mu?, physics?}}, "
                        "default?}}")]
    for k, d in world_knobs.items():
        w = f"{where}.{k}"
        if is_profile_knob(d):
            out += _profile_problems(d, w)
            continue
        if not isinstance(d, dict) or not isinstance(d.get("values"), dict) or not d["values"]:
            out.append((w, "needs values: {value: {...}}"))
            continue
        for v, m in d["values"].items():
            if m is None:
                continue
            if not isinstance(m, dict) or set(m) - set(KINDS):
                out.append((f"{w}.values.{v}", f"is a mapping of {', '.join(KINDS)}"))
                continue
            wp = m.get("weather")
            if wp is not None and (not isinstance(wp, dict) or not all(
                    isinstance(x, (int, float)) and not isinstance(x, bool) for x in wp.values())):
                out.append((f"{w}.values.{v}.weather", "is {parameter: number}"))
            if m.get("environment") is not None:
                env = environment_problems(m["environment"], f"{w}.values.{v}.environment")
                if env:
                    out += env
                    continue
            same = form_problem(k, v, m)
            if same:
                out.append((f"{w}.values.{v}", same))
                continue
            if m.get("physics") not in (None, "none"):
                out.append((f"{w}.values.{v}.physics", "is `none` (visual only) or absent"))
                continue
            why = simulator_problem(k, v, m, simulator) if simulator else None
            if why:
                out.append((f"{w}.values.{v}", why))
        if d.get("default") is not None and str(d["default"]) not in map(str, d["values"]):
            out.append((f"{w}.default", f"{d['default']!r} is not one of its values"))
    return out


def _profile_problems(d, w):
    out = []
    bad = sorted(set(d) - set(PROFILE_KEYS))
    if bad:
        out.append((w, f"{bad[0]}: a profile knob has {', '.join(PROFILE_KEYS)} (no values)"))
    if d.get("sets") not in PROFILE_FIELDS:
        out.append((f"{w}.sets", f"one of {', '.join(PROFILE_FIELDS)}"))
    r = d.get("range")
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)  # noqa: E731
    if not (isinstance(r, list) and len(r) == 2 and all(num(x) for x in r) and r[0] < r[1]):
        out.append((f"{w}.range", "[low, high], two numbers, low below high"))
    else:
        if d.get("default") is not None and not (num(d["default"]) and r[0] <= d["default"] <= r[1]):
            out.append((f"{w}.default", f"a number in its range [{r[0]}, {r[1]}]"))
        if d.get("sets") in PROFILE_FIELDS:   # the range within the field's own (092 K9e)
            out += [(f"{w}.range", why) for x in r
                    for why in [field_range_problem(d["sets"], x)] if why]
    if d.get("step") is not None and not (num(d["step"]) and d["step"] > 0):
        out.append((f"{w}.step", "a positive number (default: 1 % of the range)"))
    if d.get("min_interval") is not None and not (num(d["min_interval"])
                                                  and d["min_interval"] >= 0):
        out.append((f"{w}.min_interval", f"s between sends, a number >= 0 (default "
                                          f"{PROFILE_MIN_INTERVAL:g})"))
    return out


def simulator_problem(knob, value, m: dict, simulator: str):
    """Why `simulator` cannot apply knob `knob`'s value `value` (its mapping `m`), or None: the
    one rule `plan` refuses a run by and `problems` refuses a testbench by (issue 154)."""
    m = m or {}
    if simulator == "carla":
        if m.get("surface_map"):
            return (f"knob {knob}={value}: a surface map, which CARLA cannot apply per run; "
                    "declare a visual-only value (physics: none) for CARLA")
        if m.get("mu") is not None and m.get("physics") != "none":
            return (f"knob {knob}={value}: a friction (mu {m['mu']}), which CARLA's weather does "
                    "not change (wetness is visual); declare it physics: none to run it as a "
                    "look only")
    if simulator == "isaac" and m.get("weather"):
        return (f"knob {knob}={value}: weather parameters, but Isaac has no weather service (a "
                "scenario's EnvironmentAction sets its sky, fog and rain); declare this value "
                "without weather for Isaac")
    env = m.get("environment") if isinstance(m.get("environment"), dict) else {}
    for f in env:
        if f in PROFILE_FIELDS and simulator not in PROFILE_FIELDS[f]:
            return (f"knob {knob}={value}: environment.{f}, which the {simulator} world server "
                    f"cannot apply and read back ({', '.join(PROFILE_FIELDS[f])} only)")
    return None


def form_problem(knob, value, m: dict):
    """Why value `value` of knob `knob` sets one quantity in both forms (`environment:` and
    `weather:`), or None (092 K9e)."""
    env = (m or {}).get("environment")
    weather = (m or {}).get("weather")
    if not isinstance(env, dict) or not isinstance(weather, dict):
        return None
    for f in env:
        for p in SAME_QUANTITY.get(f, ()):
            if p in weather:
                return (f"knob {knob}={value}: environment.{f} and weather.{p} set the same "
                        "quantity: one value sets it in one form (environment: on every target, "
                        "weather: CARLA only)")
    return None


def environment_problems(env, where) -> list:
    """A static value's `environment:`, checked: {field: number}, a field a profile sets."""
    if not isinstance(env, dict) or not all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in env.values()):
        return [(where, "is {field: number}")]
    out = [(f"{where}.{f}", f"{f} is not one of {', '.join(PROFILE_FIELDS)}")
           for f in env if f not in PROFILE_FIELDS]
    out += [(f"{where}.{f}", why) for f, v in env.items()
            for why in [field_range_problem(f, v)] if why]
    return out


def plan(world_knobs: dict, knobs: dict, simulator: str, baseline: dict = None) -> dict:
    """What to send for a run's knob values: {weather: {param: value}, surface_maps: {knob:
    name}, notes: {knob: text}}. KnobError names a knob the world lacks, a value it does not
    declare, or one this simulator cannot honour."""
    weather = dict(baseline or {})
    maps, notes, environment = {}, {}, {}
    for knob, value in knobs.items():
        decl = (world_knobs or {}).get(knob)
        if decl is None:
            raise KnobError(f"knob {knob!r}: the world declares no such knob (testbench.yaml "
                            f"world.knobs: {', '.join(sorted(world_knobs or {})) or 'none'})")
        if is_profile_knob(decl):
            raise KnobError(f"knob {knob}: a profile knob (profile: true) is bound to a "
                            "profile, `time: <x> <value>; ...` or `s(<lane>): ...`, not one "
                            "parameter")
        values = {str(k): v for k, v in decl["values"].items()}
        if value not in values:
            raise KnobError(f"knob {knob}={value!r}: not a value the world declares "
                            f"({', '.join(values)})")
        m = values[value] or {}
        visual = m.get("physics") == "none"
        why = form_problem(knob, value, m) or simulator_problem(knob, value, m, simulator)
        if why:
            raise KnobError(why)
        if m.get("environment"):
            for f, x in m["environment"].items():
                off = field_range_problem(f, x)
                if off:
                    raise KnobError(f"knob {knob}={value}: environment.{f}: {off}")
            environment[knob] = {f: float(x) for f, x in m["environment"].items()}
        if visual and m.get("mu") is None:
            notes[knob] = "visual only: the friction was not applied"
        weather.update({p: float(x) for p, x in (m.get("weather") or {}).items()})
        if m.get("surface_map"):
            maps[knob] = str(m["surface_map"])
    return {"weather": weather, "surface_maps": maps, "notes": notes,
            "environment": environment}


def compare(knobs: dict, world_knobs: dict, sent: dict, read: dict, maps_read=None) -> dict:
    """result.json's `knobs`: per knob {value, applied: {param: read-back}, ok}, and `ok` over
    all. A weather parameter whose read-back differs from what was sent (beyond TOLERANCE) is
    not ok; a surface map with no read-back is `unverified`."""
    out, all_ok = {}, True
    for knob, value in knobs.items():
        m = ((world_knobs or {}).get(knob) or {}).get("values", {})
        m = {str(k): v for k, v in m.items()}.get(value) or {}
        applied, ok = {}, True
        for p in (m.get("weather") or {}):
            got = (read or {}).get(p)
            applied[p] = got
            if got is None or abs(float(got) - float(sent[p])) > TOLERANCE:
                ok = False
        entry = {"value": value, "applied": applied}
        if m.get("surface_map"):
            got = (maps_read or {}).get(knob)
            entry["surface_map"] = {"sent": m["surface_map"],
                                    "read": got if got is not None else "unverified"}
            if got is not None and got != m["surface_map"]:
                ok = False
        if m.get("physics") == "none":
            entry["physics"] = "none: the friction was not applied"
        entry["ok"] = ok
        all_ok = all_ok and ok
        out[knob] = entry
    return {"ok": all_ok, "knobs": out}


GET_WEATHER = "/scenario_world_bridge/get_weather"


def get_weather_argv() -> list:
    return ["ros2", "service", "call", GET_WEATHER, "scensim_interfaces/srv/GetWeather"]


def weather_read(text: str):
    """{name: value} from get_weather's printed response, or None when it did not answer."""
    import re
    if not re.search(r"success=True", text or ""):
        return None
    names = re.search(r"names=\[(.*?)\]", text or "", re.S)
    values = re.search(r"values=\[(.*?)\]", text or "", re.S)
    if not names or not values:
        return {}
    ns = [n.strip().strip("'\"") for n in names.group(1).split(",") if n.strip()]
    vs = [float(v) for v in values.group(1).split(",") if v.strip()]
    return dict(zip(ns, vs))
