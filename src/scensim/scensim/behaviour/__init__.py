"""Behaviour models: an entity's behaviour as a model of its own, run batched (scensim_batch)
or for one entity on seats (roadmap 092 K10; scenario-description.md section 4).

A scenario names one through its entity's ObjectController:

    <Property name="model" value="scensim.behaviour:gap_acceptance_walker"/>
    <Property name="speed" value="$walk_speed"/>

The other properties are the model's parameters (`params_schema`), which the sampler may draw.
A model is written once over an array namespace (sim_vehicle_ecu.xp: numpy on seats, torch in a
batch), so its batched form and its single-entity form are one code:

    m = gap_acceptance_walker(params, seeds, anchors, xp=namespace("torch", "cuda"))
    action, events = m.step(obs, dt)          # every slot at once

Its observation is truth only, and its action a kinematic command for its entity (speed,
heading, acceleration limit), which the world integrates. Its decisions come out as events per
slot, for the truth and the agreement check.

Coefficients are never constants in a model: a model reads a named, cited parameter set from
`sets/<name>.yaml` (`parameter_set`), and the record names the set and its sha256.
"""
import hashlib
from pathlib import Path

from .follower import IdmFollower
from .walker import GapAcceptanceWalker

SETS = Path(__file__).resolve().parent / "sets"

gap_acceptance_walker = GapAcceptanceWalker
idm_follower = IdmFollower

# the models a scenario may name; idm_follower joins when its seats and batch sides exist (K13
# steps ii and iii), so neither target takes it before then
MODELS = {"gap_acceptance_walker": GapAcceptanceWalker}


def parameter_set(name: str) -> dict:
    """The parameter set `name` (sets/<name>.yaml), with its `sha256` added."""
    import yaml

    if not name or "/" in name or name.startswith("."):
        raise ValueError(f"parameter set {name!r}: a plain name (one of {', '.join(set_names())})")
    p = SETS / f"{name}.yaml"
    if not p.is_file():
        raise ValueError(f"no parameter set {name!r} (known: {', '.join(set_names())})")
    raw = p.read_bytes()
    data = yaml.safe_load(raw)
    if data.get("name") != name:
        raise ValueError(f"{p}: names itself {data.get('name')!r}, not {name!r}")
    data["sha256"] = hashlib.sha256(raw).hexdigest()
    return data


def set_names() -> list:
    return sorted(p.stem for p in SETS.glob("*.yaml"))
