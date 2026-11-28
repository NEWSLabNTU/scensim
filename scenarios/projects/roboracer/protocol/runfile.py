"""A protocol run's `session.yaml`, the run file (scensim roadmap 091 W12): the protocol's own
fields (manoeuvre, condition, repetition, reference, rates, t0_ns, ...) and its session
conditions under `session`, a `scensim.session/1` record. Format "scensim 091 run, version 2".
The checks are scensim's (scensim.session: from this repository's src/scensim when scensim is
not installed); W23's version 1 files are refused, naming `scensim session migrate`.

    load(path) -> run file      check(doc) -> doc      migrate(v1 doc) -> v2 doc
    component_session(record) -> the drive unit's session inputs ({"battery_v": V})
"""
import sys
from pathlib import Path

try:
    from scensim import session as S
except ImportError:   # a source checkout without scensim installed
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src" / "scensim"))
    from scensim import session as S

FILE = S.RUN_FILE
FORMAT = S.RUN_FORMAT
SessionError = S.SessionError


def check(doc, where="run file"):
    return S.check_run(doc, where)


def load(path):
    return S.load_run(path)


def migrate(doc):
    return S.migrate_run(doc)


def component_session(record):
    """The session inputs the drive unit (roboracer_vesc) declares, from a run's record."""
    from sim_vehicle_ecu import component as comp
    from roboracer_vesc.component import RoboRacerVesc
    return comp.session_values(comp.declared_session(RoboRacerVesc), record, "roboracer_vesc")
