"""Session conditions (roadmap 091 W12): the schema `scensim.session/1` of a session record (the
battery, the floor, the tyres), the protocol run file that carries one (`session.yaml`, format
"scensim 091 run, version 2"), and the migration of W23's version 1 files. A scensim run's own
record is `session_record.yaml`, a bare record, so one filename never holds two shapes."""
import copy

import pytest
import yaml

from scensim import session as S

RECORD = {
    "schema": "scensim.session/1",
    "recorded": {"by": "operator", "at": "2026-11-28T15:00:00+08:00"},
    "battery": {"voltage_v": 7.92, "source": "measured", "how": "at rest, before the run"},
    "floor": {"surface": "lab_vinyl", "state": "clean", "source": "measured",
              "note": "swept 10:20"},
    "tyres": {"set": "front-A rear-A", "age": {"runs": 14, "distance_m": 2300.0},
              "since": "2026-11-20", "source": "measured"},
    "ambient": {"temperature_c": 21.5, "source": "measured"},
    "notes": "",
}

W23 = {
    "format": "scensim 091 W23 run, version 1",
    "manoeuvre": "M1", "condition": {"speed": 2.0}, "repetition": 0,
    "session": {"battery_v": 7.9, "floor": "synthetic: the twin's floor", "tyre_age": "synthetic"},
    "reference": {"kind": "twin truth", "noise_m": 0.0, "noise_rad": 0.0},
    "rates_hz": {"cmd": 50.0, "core": 50.0, "imu": 50.0, "ref": 100.0},
    "source": "the twin", "physics_hz": 120, "protocol_version": 1, "t0_ns": 5,
}


def test_a_full_record_checks():
    assert S.check(copy.deepcopy(RECORD)) == RECORD


def test_only_the_schema_line_is_required():
    assert S.check({"schema": "scensim.session/1"}) == {"schema": "scensim.session/1"}
    with pytest.raises(S.SessionError, match="schema"):
        S.check({"battery": {"voltage_v": 7.9, "source": "measured"}})
    with pytest.raises(S.SessionError, match="scensim.session/1"):
        S.check({"schema": "scensim.session/2"})


@pytest.mark.parametrize("path,value,match", [
    (("battery", "volts"), 7.9, r"battery\.volts"),             # unknown key, by name
    (("colour",), "red", "colour"),
    (("battery", "voltage_v"), -1.0, r"battery\.voltage_v"),     # not a positive number
    (("battery", "voltage_v"), "7.9", r"battery\.voltage_v"),
    (("battery", "source"), "guessed", r"battery\.source"),       # not measured/nominal/synthetic
    (("floor", "state"), "sticky", r"floor\.state"),              # not one of the states
    (("tyres", "age", "runs"), -2, r"tyres\.age\.runs"),
    (("tyres", "age", "hours"), 3, r"tyres\.age\.hours"),
    (("ambient", "temperature_c"), "warm", r"ambient\.temperature_c"),
])
def test_a_bad_field_is_refused_by_name(path, value, match):
    doc = copy.deepcopy(RECORD)
    d = doc
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value
    with pytest.raises(S.SessionError, match=match):
        S.check(doc)


def test_a_value_without_its_source_is_refused():
    doc = copy.deepcopy(RECORD)
    del doc["battery"]["source"]
    with pytest.raises(S.SessionError, match=r"battery\.source"):
        S.check(doc)


def test_every_key_is_listed_with_its_meaning():
    keys = S.keys()
    for k in ("schema", "recorded.by", "battery.voltage_v", "battery.source", "floor.state",
              "tyres.age.runs", "tyres.age.distance_m", "ambient.temperature_c", "notes"):
        assert keys[k], k
    assert "pending the user's confirmation" in keys["floor.state"]
    assert "pending the user's confirmation" in keys["tyres.age.runs"]


def test_the_template_is_a_record_that_checks():
    doc = yaml.safe_load(S.template())
    assert S.check(doc)["schema"] == "scensim.session/1"


def test_a_w23_run_file_is_refused_naming_migrate():
    with pytest.raises(S.SessionError, match="scensim session migrate"):
        S.check_run(copy.deepcopy(W23))


def test_migrate_keeps_every_value_of_a_w23_run_file():
    new = S.migrate_run(copy.deepcopy(W23))
    assert new["format"] == "scensim 091 run, version 2"
    assert S.check_run(new) == new
    rec = new["session"]
    assert rec["battery"] == {"voltage_v": 7.9, "source": "synthetic"}
    assert rec["floor"]["note"] == "synthetic: the twin's floor"
    assert rec["tyres"]["note"] == "synthetic"
    for k, v in W23.items():                     # the run's own fields, untouched
        if k not in ("format", "session"):
            assert new[k] == v, k
    assert S.migrate_run(copy.deepcopy(new)) == new   # idempotent


def test_migrate_a_directory_rewrites_each_run_file(tmp_path):
    for i in range(2):
        d = tmp_path / f"r{i}"
        d.mkdir()
        (d / "session.yaml").write_text(yaml.safe_dump(W23, sort_keys=False))
    done = S.migrate_dir(tmp_path)
    assert len(done) == 2
    for d in tmp_path.iterdir():
        assert S.load_run(d / "session.yaml")["format"] == "scensim 091 run, version 2"
    assert S.migrate_dir(tmp_path) == []          # nothing left to do


def test_a_scensim_run_names_its_bare_record_apart():
    assert S.RUN_FILE == "session.yaml" and S.RECORD_FILE == "session_record.yaml"
