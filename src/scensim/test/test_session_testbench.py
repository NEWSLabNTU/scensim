"""A testbench's session (roadmap 091 W12, E2): `session:` in testbench.yaml, a record inline or a
file in the project; it reaches the ego's control component (the Isaac ego config's
`component.session`), is part of the stack's fingerprint (a stack started under another session
is refused, naming it), is checked by `testbench check` (a component's declared session input the
record lacks is refused there, in Isaac's interpreter), and every run writes it as
`session_record.yaml` with its hash in the provenance, or says `session: null`."""
import copy
import hashlib

import pytest
import yaml

from scensim import component as comp
from scensim import project as projectmod
from scensim import session as S
from scensim import stack as stackmod

REC = {"schema": "scensim.session/1",
       "battery": {"voltage_v": 7.92, "source": "measured", "how": "at rest"}}


def test_session_is_a_testbench_key():
    assert "session" in projectmod.TOP_KEYS


def test_the_record_is_inline_or_a_file_in_the_project(tmp_path):
    assert S.resolve(tmp_path, {"session": copy.deepcopy(REC)}) == REC
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.yaml").write_text(yaml.safe_dump(REC))
    assert S.resolve(tmp_path, {"session": "sessions/a.yaml"}) == REC
    assert S.resolve(tmp_path, {}) is None
    with pytest.raises(S.SessionError, match="sessions/b.yaml"):
        S.resolve(tmp_path, {"session": "sessions/b.yaml"})
    with pytest.raises(S.SessionError, match=r"battery\.volts"):
        S.resolve(tmp_path, {"session": {"schema": "scensim.session/1",
                                         "battery": {"volts": 7.9, "source": "measured"}}})
    with pytest.raises(S.SessionError, match="a record or a file"):
        S.resolve(tmp_path, {"session": 7.9})


def test_a_bad_session_is_a_testbench_finding(tmp_path):
    found = S.problems(tmp_path, {"session": {"schema": "scensim.session/1", "colour": 1}})
    assert found and "colour" in found[0].what and found[0].refused
    assert S.problems(tmp_path, {"session": copy.deepcopy(REC)}) == []
    assert S.problems(tmp_path, {}) == []


def test_the_session_is_part_of_the_stacks_fingerprint(tmp_path):
    (tmp_path / "testbench.yaml").write_text("simulator: isaac\n")
    a = stackmod.fingerprint(tmp_path, {"session": copy.deepcopy(REC)}, build={})
    b = stackmod.fingerprint(tmp_path, {"session": dict(REC, notes="other")}, build={})
    none = stackmod.fingerprint(tmp_path, {}, build={})
    assert a["session"] != b["session"] and none["session"] is None
    assert any(d.startswith("session:") for d in stackmod.fingerprint_diff(a, b))
    assert stackmod.fingerprint_diff(a, copy.deepcopy(a)) == []


def test_the_ego_config_carries_the_record_to_the_component():
    rec = {"entry_point": "my_racer.sample", "paths": []}
    assert comp.ego_entry(rec, REC)["session"] == REC
    assert "session" not in comp.ego_entry(rec)
    # refused at testbench check, in Isaac's Python: making the component raises sim_vehicle_ecu's
    # ComponentError for a declared session input the record lacks, reported as a config error
    script = comp.CHECK_SCRIPT
    made = script.index("c = rig.make_component()")
    guard = script.rfind("try:", 0, made)
    assert guard != -1 and "except components.ComponentError" in script[made:made + 200]
    assert "session_values" not in script


def test_a_run_writes_the_record_and_its_hash(tmp_path):
    prov = S.write_record(tmp_path, REC)
    text = (tmp_path / S.RECORD_FILE).read_text()
    assert yaml.safe_load(text) == REC
    assert prov == {"file": S.RECORD_FILE, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    other = tmp_path / "none"
    other.mkdir()
    assert S.write_record(other, None) is None and not (other / S.RECORD_FILE).exists()
