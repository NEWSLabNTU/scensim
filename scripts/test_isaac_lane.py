"""Issue 186: scripts/isaac_lane.sh says loudly when the Isaac-Python lane does not run, and the
lane's suites import no pytest at the top level (Isaac's venv has none; issue 090's convention)."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "scripts" / "isaac_lane.sh"
SUITES = ["src/scensim_isaac_world/test", "src/scensim_sampler/test", "src/scensim_batch/test"]


def run(tmp_path, isaac_root):
    env = {"HOME": os.environ.get("HOME", "/tmp"), "USER": os.environ.get("USER", "u"),
           "PATH": "/usr/bin:/bin"}
    if isaac_root is not None:
        env["ISAAC_ROOT"] = str(isaac_root)
    status = tmp_path / "status"
    p = subprocess.run(["bash", str(LANE), str(status)], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=120)
    return p, status.read_text().strip()


def test_unset_isaac_root_is_not_run_loudly(tmp_path):
    p, status = run(tmp_path, None)
    assert p.returncode == 0
    assert status.startswith("NOT RUN: the Isaac-Python lane") and status.endswith("ISAAC_ROOT unset")
    assert "NOT RUN: the Isaac-Python lane" in p.stderr and "####" in p.stderr
    assert "issue 186" in p.stderr


def test_isaac_root_without_a_venv_names_the_path(tmp_path):
    p, status = run(tmp_path, tmp_path / "nowhere")
    assert p.returncode == 0
    assert status.endswith(f"ISAAC_ROOT={tmp_path / 'nowhere'}, no venv/bin/activate")
    assert str(tmp_path / "nowhere") in p.stderr


def test_an_install_that_does_not_work_fails_the_lane_not_skips_it(tmp_path):
    """A venv/bin/activate is there, so the lane runs; isaac_env.sh refuses the stub (no Isaac
    Sim in it), and the lane fails with FAILED in its status, not NOT RUN."""
    act = tmp_path / "isaac" / "venv" / "bin" / "activate"
    act.parent.mkdir(parents=True)
    act.write_text("")
    p, status = run(tmp_path, tmp_path / "isaac")
    assert p.returncode != 0
    assert status.startswith("FAILED: the Isaac-Python lane")
    assert "not an Isaac Sim install" in p.stdout + p.stderr


def test_the_lanes_suites_import_no_pytest_at_the_top_level():
    """Except behind a SkipTest guard (test_installed's `try: import pytest / except ImportError:
    raise unittest.SkipTest(...)`)."""
    bad = []
    for d in SUITES:
        for f in sorted((ROOT / d).glob("*.py")):
            text = f.read_text()
            for m in re.finditer(r"^(import pytest|from pytest import)", text, re.M):
                after = text[m.end():m.end() + 400]
                guarded = re.search(r"except ImportError:[^\n]*\n\s+raise unittest\.SkipTest", after)
                if not guarded:
                    bad.append(str(f.relative_to(ROOT)))
    assert bad == []


def stub_install(root, record):
    """An install isaac_env.sh accepts (a venv/bin/activate, Isaac Sim's package directory)
    whose activate puts a fake python3 first: it records OMP_NUM_THREADS and MKL_NUM_THREADS to
    `record` and passes every suite with one test."""
    (root / "venv" / "lib" / "python3.12" / "site-packages" / "isaacsim").mkdir(parents=True)
    bin_ = root / "stubbin"
    bin_.mkdir()
    py = bin_ / "python3"
    py.write_text("#!/bin/bash\n"
                  f'echo "${{OMP_NUM_THREADS-unset}} ${{MKL_NUM_THREADS-unset}}" >> "{record}"\n'
                  'case "$*" in *unittest*) printf "Ran 1 test in 0.001s\\n\\nOK\\n" >&2 ;; esac\n')
    py.chmod(0o755)
    (root / "venv" / "bin").mkdir(parents=True)
    (root / "venv" / "bin" / "activate").write_text(f'export PATH="{bin_}:$PATH"\n')


def test_the_lane_passes_the_thread_cap_through_its_clean_environment(tmp_path):
    """Issue 188: `just test` caps OMP_NUM_THREADS and MKL_NUM_THREADS; the lane's env -i must
    keep them, or Isaac's Python runs one thread per core again."""
    record = tmp_path / "threads"
    stub_install(tmp_path / "isaac", record)
    env = {"HOME": os.environ.get("HOME", "/tmp"), "USER": os.environ.get("USER", "u"),
           "PATH": "/usr/bin:/bin", "ISAAC_ROOT": str(tmp_path / "isaac"),
           "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "2"}
    status = tmp_path / "status"
    p = subprocess.run(["bash", str(LANE), str(status)], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    assert status.read_text().startswith("Isaac-Python lane: ran (3 tests in 3 suites, OK)")
    lines = record.read_text().split("\n")
    assert [x for x in lines if x] == ["3 2"] * 4    # the numpy line and the three suites
