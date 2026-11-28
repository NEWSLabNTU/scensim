"""Session conditions (roadmap 091 W12): what a run, or a real car's log, was made under.

A **session record** (schema ``scensim.session/1``) names the battery, the floor and the tyres:

    schema: scensim.session/1
    recorded: {by: operator, at: "2026-11-28T15:00:00+08:00"}
    battery:  {voltage_v: 7.92, source: measured, how: "at rest, before the run"}
    floor:    {surface: lab_vinyl, state: clean, source: measured, note: "swept 10:20"}
    tyres:    {set: "front-A rear-A", age: {runs: 14, distance_m: 2300}, since: 2026-11-20,
               source: measured}
    ambient:  {temperature_c: 21.5, source: measured}
    notes: ""

Only ``schema`` is required: a part left out was not recorded. Each part's values have their
unit in their name and say where they came from (``source``: measured, nominal or synthetic).
Every key is listed with its meaning by ``keys()`` (``scensim session keys``); an unknown one is
refused by name. The floor states and the tyre-age units are drafts, pending the user's
confirmation.

Where records live:

- a protocol run (a real car's log, or a twin run from the project's tools): ``session.yaml``
  beside the bag, the **run file**: the protocol's own fields (manoeuvre, condition,
  repetition, reference, rates, ...) with the record under ``session``; format ``scensim 091
  run, version 2``. W23's version 1 files are refused, naming ``scensim session migrate``;
- a scensim run: ``session_record.yaml`` in the run's directory, the bare record (the
  testbench's ``session:``). Two names, so that one filename never holds two shapes.

A component may declare the battery's voltage as an input (sim_vehicle_ecu SESSION_INPUTS); it
is read from a record's ``battery.voltage_v``.
"""
import math
from pathlib import Path

import yaml

SCHEMA = "scensim.session/1"
RUN_FORMAT = "scensim 091 run, version 2"
W23_FORMAT = "scensim 091 W23 run, version 1"
RUN_FILE = "session.yaml"
RECORD_FILE = "session_record.yaml"

SOURCES = ("measured", "nominal", "synthetic")
# pending the user's confirmation (133, 2026-11-28)
FLOOR_STATES = ("clean", "dusty", "damp", "wet", "other")
PENDING = " (pending the user's confirmation)"

# key: (kind, meaning). Kinds: str, pos (a number > 0), num (any finite number), count (an
# integer >= 0), dist (a number >= 0), source, state; a mapping is a part with its own keys.
FIELDS = {
    "schema": ("schema", f"the record's schema: {SCHEMA}"),
    "recorded": {
        "by": ("str", "who recorded the session"),
        "at": ("str", "when, ISO 8601 with its offset"),
    },
    "battery": {
        "voltage_v": ("pos", "V: the pack's voltage at the session's start (a component's "
                             "session input battery_v)"),
        "source": ("source", "where the voltage came from: " + ", ".join(SOURCES)),
        "how": ("str", "how it was measured (at rest, under load, the meter)"),
    },
    "floor": {
        "surface": ("str", "the floor's surface: the stage's scensim:surface or material name"),
        "state": ("state", "the floor's state: " + ", ".join(FLOOR_STATES) + PENDING),
        "source": ("source", "where the state came from: " + ", ".join(SOURCES)),
        "note": ("str", "free text: when it was cleaned, what is on it"),
    },
    "tyres": {
        "set": ("str", "which tyres, by the user's own names"),
        "age": {
            "runs": ("count", "runs on this set since it was fitted" + PENDING),
            "distance_m": ("dist", "m driven on this set since it was fitted" + PENDING),
        },
        "since": ("str", "when the set was fitted, ISO 8601 date"),
        "source": ("source", "where the age came from: " + ", ".join(SOURCES)),
        "note": ("str", "free text"),
    },
    "ambient": {
        "temperature_c": ("num", "deg C: the room's temperature"),
        "source": ("source", "where it came from: " + ", ".join(SOURCES)),
    },
    "notes": ("str", "free text"),
}
# a part with values needs its source
SOURCED = ("battery", "floor", "tyres", "ambient")


class SessionError(ValueError):
    """A record or run file that does not check; the message names the key and the fix."""


def keys(fields=FIELDS, prefix=""):
    """Every key, dotted, with its meaning."""
    out = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            out.update(keys(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v[1]
    return out


def _value(kind, v, key):
    def bad(want):
        return SessionError(f"session {key} = {v!r}: {want}")
    if kind == "schema":
        if v != SCHEMA:
            raise bad(f"must be {SCHEMA}")
    elif kind == "str":
        if not isinstance(v, str):
            raise bad("a string")
    elif kind in ("pos", "num", "dist", "count"):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise bad("a number")
        if kind == "pos" and v <= 0:
            raise bad("a number > 0")
        if kind == "dist" and v < 0:
            raise bad("a number >= 0")
        if kind == "count" and (not isinstance(v, int) or v < 0):
            raise bad("an integer >= 0")
    elif kind == "source":
        if v not in SOURCES:
            raise bad("one of " + ", ".join(SOURCES))
    elif kind == "state":
        if v not in FLOOR_STATES:
            raise bad("one of " + ", ".join(FLOOR_STATES))


def _walk(doc, fields, prefix):
    if not isinstance(doc, dict):
        raise SessionError(f"session {prefix.rstrip('.') or 'record'}: a mapping, is {doc!r}")
    for k, v in doc.items():
        key = f"{prefix}{k}"
        if k not in fields:
            raise SessionError(f"session {key}: unknown key; known here: "
                               f"{', '.join(fields)} (scensim session keys)")
        if isinstance(fields[k], dict):
            _walk(v, fields[k], key + ".")
        else:
            _value(fields[k][0], v, key)


def check(doc, where="session record"):
    """The record `doc`, checked (SessionError otherwise); returned as given."""
    if not isinstance(doc, dict) or "schema" not in doc:
        raise SessionError(f"{where}: no schema line; a session record starts "
                           f"`schema: {SCHEMA}`")
    _walk(doc, FIELDS, "")
    for part in SOURCED:
        if part in doc and set(doc[part]) - {"source", "note", "how"} and "source" not in doc[part]:
            raise SessionError(f"session {part}.source: missing; say where the values came "
                               f"from: {', '.join(SOURCES)}")
    return doc


def template():
    """A record to fill in, as text (``scensim session new``)."""
    return (f"schema: {SCHEMA}\n"
            "recorded: {by: \"\", at: \"\"}          # who, and when (ISO 8601 with its offset)\n"
            "battery: {voltage_v: 7.9, source: nominal, how: \"\"}   # measure it: source: measured\n"
            "# floor: {surface: \"\", state: clean, source: measured, note: \"\"}\n"
            "# tyres: {set: \"\", age: {runs: 0, distance_m: 0}, since: \"\", source: measured}\n"
            "# ambient: {temperature_c: 20.0, source: measured}\n"
            "notes: \"\"\n")


def load(path):
    """A bare record from `path`, checked."""
    return check(yaml.safe_load(Path(path).read_text()), str(path))


# --- the protocol run file ---------------------------------------------------------------

def check_run(doc, where="run file"):
    """A protocol run file (version 2), its record checked; W23's version 1 is refused."""
    if not isinstance(doc, dict):
        raise SessionError(f"{where}: a mapping")
    fmt = doc.get("format")
    if fmt == W23_FORMAT:
        raise SessionError(f"{where}: {W23_FORMAT!r}, before session records; rewrite it with "
                           "`scensim session migrate <dir>` (every value is kept)")
    if fmt != RUN_FORMAT:
        raise SessionError(f"{where}: format {fmt!r}, not {RUN_FORMAT!r}")
    check(doc.get("session"), f"{where}: session")
    return doc


def load_run(path):
    """A protocol run file from `path`, checked."""
    return check_run(yaml.safe_load(Path(path).read_text()), str(path))


def migrate_run(doc):
    """A W23 version 1 run file as version 2, every value kept: its free-form `session`
    (battery_v, floor, tyre_age, all synthetic in W23) becomes a record. A version 2 file is
    returned as it is."""
    if doc.get("format") == RUN_FORMAT:
        return doc
    if doc.get("format") != W23_FORMAT:
        raise SessionError(f"format {doc.get('format')!r}: neither {W23_FORMAT!r} nor "
                           f"{RUN_FORMAT!r}")
    old = dict(doc.get("session") or {})
    rec = {"schema": SCHEMA}
    if "battery_v" in old:
        rec["battery"] = {"voltage_v": float(old.pop("battery_v")), "source": "synthetic"}
    if "floor" in old:
        rec["floor"] = {"note": str(old.pop("floor"))}
    if "tyre_age" in old:
        rec["tyres"] = {"note": str(old.pop("tyre_age"))}
    if old:
        raise SessionError(f"W23 session keys this migration does not know: {sorted(old)}")
    out = {}
    for k, v in doc.items():
        out[k] = RUN_FORMAT if k == "format" else rec if k == "session" else v
    if "session" not in out:
        out["session"] = rec
    return check_run(out)


def migrate_dir(root):
    """Every W23 run file under `root` rewritten as version 2; the paths rewritten."""
    done = []
    for p in sorted(Path(root).rglob(RUN_FILE)):
        doc = yaml.safe_load(p.read_text())
        if isinstance(doc, dict) and doc.get("format") == W23_FORMAT:
            p.write_text(yaml.safe_dump(migrate_run(doc), sort_keys=False))
            done.append(p)
    return done


# --- a testbench's session and a run's record (E2) ----------------------------------------

def resolve(project, settings):
    """The testbench's session record: `session:` inline (a record) or a file in the project
    (a path relative to it); None when the testbench names none. SessionError otherwise."""
    v = (settings or {}).get("session")
    if v is None:
        return None
    if isinstance(v, dict):
        return check(v, "testbench.yaml session")
    if isinstance(v, str):
        p = Path(project) / v
        if not p.is_file():
            raise SessionError(f"testbench.yaml session: {v}: no such file in the project")
        return load(p)
    raise SessionError(f"testbench.yaml session: {v!r}: a record or a file in the project "
                       f"(`scensim session new > sessions/<name>.yaml`)")


def problems(project, settings):
    """`testbench check`'s findings for the testbench's session: a bad one is refused."""
    from scensim.findings import Finding
    try:
        resolve(project, settings)
    except SessionError as e:
        return [Finding("testbench.yaml", str(e), "scensim session keys; scensim session new",
                        refused=True)]
    return []


def text_of(record):
    """The record as written: the text its hash is of."""
    return yaml.safe_dump(record, sort_keys=False)


def sha256(record):
    import hashlib
    return None if record is None else hashlib.sha256(text_of(record).encode()).hexdigest()


def write_record(run_dir, record):
    """A run's record: `record` as ``session_record.yaml`` in `run_dir`, and the provenance's
    ``session`` block {file, sha256}; None (and no file) when the testbench named none."""
    if record is None:
        return None
    text = text_of(record)
    (Path(run_dir) / RECORD_FILE).write_text(text)
    return {"file": RECORD_FILE, "sha256": sha256(record)}


def main(argv=None):
    """``scensim session keys | new | check <file> | migrate <dir>``."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="scensim session", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keys", help="every key of a session record, with its meaning")
    sub.add_parser("new", help="a record to fill in, on stdout")
    c = sub.add_parser("check", help="check a record or a protocol run file")
    c.add_argument("file")
    m = sub.add_parser("migrate", help="rewrite W23's version 1 run files as version 2")
    m.add_argument("dir")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "keys":
            for k, v in keys().items():
                print(f"{k}: {v}")
        elif a.cmd == "new":
            sys.stdout.write(template())
        elif a.cmd == "check":
            doc = yaml.safe_load(Path(a.file).read_text())
            (check_run if isinstance(doc, dict) and "format" in doc else check)(doc, a.file)
            print(f"{a.file}: ok")
        else:
            for p in migrate_dir(a.dir):
                print(f"migrated {p}")
    except SessionError as e:
        print(f"scensim session: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
