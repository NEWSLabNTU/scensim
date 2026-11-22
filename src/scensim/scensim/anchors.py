"""A project's world anchors (roadmap 092 K9): the project's own (`testbench.yaml` world.anchors,
stated numbers) and its maps' (`assets/maps/<map>/anchors.resolved.json`, resolved by each
map's author), merged by name; and the check `testbench check` makes of a scenario's bindings
(FileHeader `scensim.anchor.<parameter>`) against them.

A resolved anchor's `source` names the file read (map, map digest, file digest) and, when the
project's `scensim.lock` holds that file with the same digest, the dataset and commit it came
from (`dataset`, `commit`): the map revision a record's geometry was read from (K9d).
"""
from pathlib import Path

from scensim import config

BIND = "scensim.anchor."


def world_anchors(project: Path):
    """The project's world anchors (testbench.yaml world.anchors; 093 gap 7), or None."""
    p = Path(project) / config.PROJECT_FILE
    if not p.is_file():
        return None
    world = (config.read_yaml(p) or {}).get("world") or {}
    return world.get("anchors") if isinstance(world, dict) else None


def _lock_revision(project: Path, name: str, file_sha256: str):
    """{dataset, commit} of the lock's dataset entry that holds `<name>/anchors.resolved.json`
    with this digest, or None (a path asset, a host's own copy that differs, no lock)."""
    from scensim import assets as assetsmod   # noqa: PLC0415
    from scensim_sampler import anchors as A  # noqa: PLC0415
    try:
        lock = assetsmod.read_lock(project)
    except (assetsmod.AssetError, OSError, ValueError):
        return None
    for entry in (lock.get("datasets") or {}).values():
        files = entry.get("files") or {}
        if files.get(f"{name}/{A.RESOLVED}") == f"sha256:{file_sha256}":
            return {"dataset": entry.get("repo"), "commit": entry.get("commit")}
    return None


def for_map(project: Path, name):
    """The anchors a scenario on map `name` reads: world.anchors and the map's resolved file
    (refused, AnchorError, when resolved on other map bytes), merged by name."""
    from scensim_sampler import anchors as A  # noqa: PLC0415
    resolved = None
    if name:
        md = Path(project) / "assets" / "maps" / name
        f = md / A.RESOLVED
        if f.is_file():
            resolved = A.load_resolved(f, map_dir=md)
            rev = None
            for a in resolved.values():
                if rev is None:
                    rev = _lock_revision(project, name, a["source"]["file_sha256"]) or {}
                a["source"].update(rev)
    return A.merge(world_anchors(project), resolved)


def binding_problems(scenario_path: Path, anchors) -> list:
    """[(message, fix)] for a scenario's bindings that the world cannot satisfy, checked as far
    as they can be without a sample: the binding's form, its parameters declared, an anchor or
    attribute the world lacks, a bare heading on a resolved lane, a function on a stated anchor,
    a constant s off its lane. A `$parameter` anchor or argument is checked per run."""
    from scensim_sampler import anchors as A  # noqa: PLC0415
    from scensim_sampler.dist import SpecError  # noqa: PLC0415
    from scensim_sampler.xosc import Scenario  # noqa: PLC0415
    try:
        sc = Scenario(scenario_path)
    except SpecError as e:
        return [(str(e), None)]
    if not sc.anchor_bindings:
        return []
    try:
        numbers, functions = A.env(anchors or {})
    except A.AnchorError as e:
        return [(str(e), "fix testbench.yaml world.anchors")]
    known = sorted({k.split(".")[1] for k in list(numbers) + list(functions)})
    world = ", ".join(known) if known else "none"
    out = []
    for param, text in sc.anchor_bindings.items():
        where = f"{BIND}{param} = {text}"
        ref, attr, arg = A.parse_binding(text, where)
        if ref.startswith("$"):
            continue
        dotted = f"anchor.{ref}.{attr}"
        if arg is None:
            if dotted in numbers:
                continue
            if dotted in functions:
                out.append((f"{where}: {dotted} is read at a lane position",
                            f"{ref}.{attr}(<s>)"))
            else:
                out.append((f"{where}: the world has no anchor attribute {dotted} (its "
                            f"anchors: {world})", "declare it in the map's anchors.yaml, or "
                            "in testbench.yaml world.anchors"))
            continue
        if dotted not in functions:
            why = ("a stated anchor has numbers only" if f"anchor.{ref}." in " ".join(numbers)
                   else f"the world has no such anchor (its anchors: {world})")
            out.append((f"{where}: {dotted}(...): {why}",
                        "a lane in the map's anchors.yaml has heading, lanelet_at, local_s"))
            continue
        if not arg.startswith("$"):
            try:
                functions[dotted](float(arg))
            except A.AnchorError as e:
                out.append((f"{where}: {e}", None))
    return out
