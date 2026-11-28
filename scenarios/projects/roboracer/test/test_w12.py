"""091 W12 in the project's tools: a run's `session.yaml` is the protocol's run file (format
"scensim 091 run, version 2"), its session conditions a `scensim.session/1` record. The tools
read it through `protocol/runfile.py` (scensim.session's checks: W23's version 1 is refused,
naming `scensim session migrate`), and twin_runs writes it, its record from `--session` (a
record file) or, with none, a synthetic one."""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "protocol"), str(ROOT / "tools")]
import runfile  # noqa: E402

V1 = {"format": "scensim 091 W23 run, version 1", "manoeuvre": "M1", "condition": {"speed": 2.0},
      "repetition": 0, "session": {"battery_v": 7.9, "floor": "synthetic: the twin's floor",
                                   "tyre_age": "synthetic"},
      "reference": {"kind": "twin truth", "noise_m": 0.0, "noise_rad": 0.0}}


def run_dir(tmp_path, doc, name="r0"):
    d = tmp_path / name
    d.mkdir()
    (d / "session.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    np.savez_compressed(d / "streams.npz", cmd_t=np.zeros(1))
    return d


def test_a_version_1_run_file_is_refused_naming_migrate(tmp_path):
    d = run_dir(tmp_path, V1)
    with pytest.raises(ValueError, match="scensim session migrate"):
        runfile.load(d / "session.yaml")
    import compare_runs
    with pytest.raises(ValueError, match="scensim session migrate"):
        compare_runs.load_runs(tmp_path)


def test_a_migrated_run_file_loads_with_its_record(tmp_path):
    d = run_dir(tmp_path, runfile.migrate(V1))
    doc = runfile.load(d / "session.yaml")
    assert doc["session"]["battery"] == {"voltage_v": 7.9, "source": "synthetic"}
    import compare_runs
    [(sess, st)] = compare_runs.load_runs(tmp_path)
    assert sess["manoeuvre"] == "M1" and "cmd_t" in st


def test_twin_runs_records_the_given_session_or_a_synthetic_one(tmp_path):
    import twin_runs
    rec = twin_runs.session_record(None)
    assert rec["battery"] == {"voltage_v": 7.9, "source": "synthetic"}
    f = tmp_path / "s.yaml"
    f.write_text(yaml.safe_dump({"schema": "scensim.session/1",
                                 "battery": {"voltage_v": 8.2, "source": "measured"}}))
    assert twin_runs.session_record(str(f))["battery"]["voltage_v"] == 8.2
    f.write_text(yaml.safe_dump({"battery_v": 8.2}))   # W23's free-form mapping: refused
    with pytest.raises(ValueError, match="schema"):
        twin_runs.session_record(str(f))
    doc = twin_runs.run_file({"manoeuvre": "M1", "condition": {"speed": 2.0}, "repetition": 0},
                             rec, {"kind": "twin truth", "noise_m": 0.0, "noise_rad": 0.0})
    assert runfile.check(doc)["format"] == "scensim 091 run, version 2"
    assert twin_runs.component_session(rec) == {"battery_v": 7.9}


def test_twin_runs_hands_kit_its_settings_from_the_environment():
    """118, 2026-11-28: the regression's env -i dropped CUDA_VISIBLE_DEVICES and ISAAC_KIT_ARGS, so
    Kit took every GPU (its multi-GPU renderer sees all cards through Vulkan). twin_runs passes
    ISAAC_KIT_ARGS to SimulationApp; the regression script carries both variables through."""
    import twin_runs
    base = ["--/crashreporter/url="]
    assert twin_runs.kit_args({}) == base
    pin = "--/renderer/multiGpu/enabled=false --/renderer/activeGpu=0"
    assert twin_runs.kit_args({"ISAAC_KIT_ARGS": pin}) == base + pin.split()
    script = (ROOT / "tools" / "w23_regression.sh").read_text()
    for line in [ln for ln in script.splitlines() if "env -i" in ln]:
        assert "CUDA_VISIBLE_DEVICES=" in line and "ISAAC_KIT_ARGS=" in line, line
