"""Knob profiles in a scenario (roadmap 092 K9; scenario-description.md section 3): a world knob
whose value changes over the run, bound in the FileHeader instead of to one parameter:

    <Property name="scensim.knob.visibility"
              value="s(west_street): 0 1000; $fog_start 1000; $fog_end $visibility_min"/>
    <Property name="scensim.knob.visibility" value="time: 0 1000; 12 1000; 20 80"/>

`<coordinate>: <x> <value>; ...`, piecewise linear between the breakpoints and held beyond the
ends. The coordinate is `time` (SSv2's simulation time, s) or `s(<lane>)` (the ego's lane
position on a lane anchor, m); each x and value is a number or a `$parameter`. The world says
what a knob's value sets (testbench.yaml world.knobs, `profile: true`); the bridge applies it
each frame. Standard library only.
"""
import re

TIME = "time"
_COORD = re.compile(r"^\s*(time|s\(\s*([A-Za-z_]\w*)\s*\))\s*:(.*)$", re.S)
_TOKEN = re.compile(r"^(\$[A-Za-z_]\w*|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)$")


class ProfileError(ValueError):
    pass


def is_profile(text):
    """Whether a knob binding's value is a profile (not `$parameter`)."""
    return bool(_COORD.match(text or ""))


def parse(text, where="profile"):
    """(coordinate, lane or None, [(x, value)]) with each x and value a float or "$name"."""
    m = _COORD.match(text or "")
    if not m:
        raise ProfileError(f"{where}: {text!r}: a profile is `time: <x> <value>; ...` or "
                           f"`s(<lane>): <x> <value>; ...`")
    coordinate = TIME if m.group(1) == TIME else "s"
    lane = m.group(2)
    points = []
    for i, part in enumerate(p for p in m.group(3).split(";") if p.strip()):
        toks = part.split()
        if len(toks) != 2 or not all(_TOKEN.match(t) for t in toks):
            raise ProfileError(f"{where}: breakpoint {i + 1} {part.strip()!r}: `<x> <value>`, "
                               f"each a number or $parameter")
        points.append(tuple(t if t.startswith("$") else float(t) for t in toks))
    if not points:
        raise ProfileError(f"{where}: no breakpoints")
    return coordinate, lane, points


def parameters(points):
    """The $parameters a profile's breakpoints read, without the `$`."""
    return sorted({t[1:] for p in points for t in p if isinstance(t, str)})


def evaluate(points, values, where="profile"):
    """[(x, value)] with each $parameter replaced by its value in `values`; ProfileError for one
    missing or not a number, or breakpoints that do not increase."""
    out = []
    for p in points:
        row = []
        for t in p:
            if isinstance(t, str):
                v = values.get(t[1:])
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ProfileError(f"{where}: {t} is not a number ({v!r})") from None
                row.append(v)
            else:
                row.append(t)
        out.append(tuple(row))
    if any(b[0] < a[0] for a, b in zip(out, out[1:])):
        raise ProfileError(f"{where}: breakpoints do not increase "
                           f"({', '.join(f'{x:g}' for x, _ in out)})")
    return out
