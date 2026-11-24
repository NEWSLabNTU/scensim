"""_dds_domain: each test run holds a DDS domain of its own (issue 155)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

HOLDER = """
import sys, time
sys.path.insert(0, {here!r})
import _dds_domain
_dds_domain.LOCK_DIR = {locks!r}
print(_dds_domain.take(), flush=True)
time.sleep(30)
"""


def fresh(monkeypatch, tmp_path, **env):
    """A separate copy of the module (the run's own keeps its domain), its locks in
    ``tmp_path``; the environment it changes is restored after the test."""
    for k in ("ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY", "CYCLONEDDS_URI", "RMW_IMPLEMENTATION"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("_dds_domain_copy", HERE / "_dds_domain.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.LOCK_DIR = str(tmp_path / "locks")
    return m


def test_two_runs_at_once_hold_different_domains_issue_155(tmp_path):
    code = HOLDER.format(here=str(HERE), locks=str(tmp_path / "locks"))
    procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
             for _ in range(2)]
    try:
        domains = [int(p.stdout.readline()) for p in procs]
    finally:
        for p in procs:
            p.kill()
            p.wait()
    assert domains[0] != domains[1]
    assert all(60 <= d <= 99 for d in domains)


def test_the_domain_is_set_on_localhost_and_the_cyclone_profile_removed_issue_155(
        monkeypatch, tmp_path):
    m = fresh(monkeypatch, tmp_path, CYCLONEDDS_URI="file:///profile.xml")
    d = m.take()
    assert os.environ["ROS_DOMAIN_ID"] == str(d) and os.environ["ROS_LOCALHOST_ONLY"] == "1"
    assert "CYCLONEDDS_URI" not in os.environ
    assert m.take() == d   # one domain per process


def test_an_rmw_off_the_rtps_port_mapping_is_refused_issue_155(monkeypatch, tmp_path):
    m = fresh(monkeypatch, tmp_path, RMW_IMPLEMENTATION="rmw_zenoh_cpp")
    with pytest.raises(RuntimeError, match="rmw_zenoh_cpp"):
        m.take()


def test_no_free_domain_fails_by_name_and_never_falls_back_issue_155(monkeypatch, tmp_path):
    code = HOLDER.format(here=str(HERE), locks=str(tmp_path / "locks"))
    code = code.replace("import _dds_domain\n",
                        "import _dds_domain\n_dds_domain.DOMAINS = range(60, 62)\n")
    procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
             for _ in range(2)]
    try:
        assert sorted(int(p.stdout.readline()) for p in procs) == [60, 61]
        m = fresh(monkeypatch, tmp_path)
        m.DOMAINS = range(60, 62)
        with pytest.raises(RuntimeError, match="no free test domain in 60-61"):
            m.take()
        assert "ROS_DOMAIN_ID" not in os.environ
    finally:
        for p in procs:
            p.kill()
            p.wait()


def test_the_two_copies_are_identical_issue_155():
    other = HERE.parents[1] / "scensim_launch" / "test" / "_dds_domain.py"
    if not other.exists():
        pytest.skip("scensim_launch's tests are not beside this package")
    assert other.read_text() == (HERE / "_dds_domain.py").read_text()
