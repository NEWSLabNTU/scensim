"""scripts/gate.sh (issue 191) against a stub `just` in a throwaway repository: no real build."""
import os
import subprocess
from pathlib import Path

GATE = Path(__file__).resolve().parent / "gate.sh"

STUB = """#!/bin/bash
# a stub `just`: STUB_FAIL=<step> fails that step, STUB_DIRTY=<step> changes a tracked file,
# STUB_FIRST=<line> prints that line before a failing step's last one,
# STUB_LANE=ran|skipped picks `just test`'s last line
step=$1
[ "${STUB_FAIL:-}" = "$step" ] && { [ -n "${STUB_FIRST:-}" ] && echo "$STUB_FIRST"; echo "$step broke"; exit 3; }
[ "${STUB_DIRTY:-}" = "$step" ] && echo dirt >> tracked.txt
if [ "$step" = test ]; then
    if [ "${STUB_LANE:-ran}" = ran ]; then
        echo "just test: done; Isaac-Python lane: ran (937 tests in 3 suites, OK)"
    else
        echo "just test: done; NOT RUN: the Isaac-Python lane: ISAAC_ROOT unset"
    fi
fi
echo "$step ok"
"""


def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / "tracked.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(r), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "one"], check=True, env=env)
    stub = tmp_path / "just-stub"
    stub.write_text(STUB)
    stub.chmod(0o755)
    return r, stub


def gate(r, stub, tmp_path, dirname="g", isaac=None, **stub_env):
    # the stub's own settings reach it through the clean environment's only door: a wrapper
    wrapper = tmp_path / f"just-{dirname}"
    exports = "".join(f"export {k}={v}\n" for k, v in stub_env.items())
    wrapper.write_text(f"#!/bin/bash\n{exports}exec {stub} \"$@\"\n")
    wrapper.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "ISAAC_ROOT"}
    env.update(GATE_JUST=str(wrapper), SCENSIM_GATE_ROOT=str(tmp_path / "gates"))
    if isaac:
        env["ISAAC_ROOT"] = isaac
    d = tmp_path / "gates" / dirname
    p = subprocess.run(["bash", str(GATE), "HEAD", str(d)], cwd=r, env=env,
                       capture_output=True, text=True)
    return p, d


def test_a_clean_gate_passes_and_names_the_commit_and_versions(tmp_path):
    r, stub = repo(tmp_path)
    p, d = gate(r, stub, tmp_path, isaac="/somewhere")
    assert p.returncode == 0, p.stderr
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    line = p.stdout.strip().splitlines()[-1]
    assert line.startswith(f"gate ok {sha} tree ")
    assert "build test check clean; Isaac lane ran (937 tests)" in line
    assert "colcon-cargo-ros2 " in line and "rustfmt " in line
    assert (d / "gate.txt").read_text().strip() == line
    assert "status after check: []" in (d / "gate.log").read_text()


def test_without_isaac_the_summary_says_so(tmp_path):
    r, stub = repo(tmp_path)
    p, _ = gate(r, stub, tmp_path, STUB_LANE="skipped")
    assert p.returncode == 0, p.stderr
    assert "Isaac lane: not on this host (ISAAC_ROOT unset)" in p.stdout


def test_a_skipped_lane_fails_where_isaac_is_set(tmp_path):
    r, stub = repo(tmp_path)
    p, d = gate(r, stub, tmp_path, isaac="/somewhere", STUB_LANE="skipped")
    assert p.returncode == 1
    assert "at test: ISAAC_ROOT is set but the Isaac-Python lane did not run" in p.stderr
    assert (d / "gate.txt").read_text().startswith("gate FAILED ")


def test_a_dirty_tree_after_a_step_fails_naming_it(tmp_path):
    r, stub = repo(tmp_path)
    p, _ = gate(r, stub, tmp_path, STUB_DIRTY="build")
    assert p.returncode == 1
    assert "at build: tracked changes after the step:" in p.stderr
    assert "tracked.txt" in p.stderr


def test_a_failing_step_fails_the_gate(tmp_path):
    r, stub = repo(tmp_path)
    p, _ = gate(r, stub, tmp_path, STUB_FAIL="check")
    assert p.returncode == 1
    assert "at check: `just check` exited non-zero (last line: check broke)" in p.stderr
    assert "first:" not in p.stderr


def test_a_failing_step_quotes_its_first_diff_line(tmp_path):
    r, stub = repo(tmp_path)
    p, _ = gate(r, stub, tmp_path, STUB_FAIL="check",
                STUB_FIRST="'Diff in src/profiles.rs:521:'")
    assert p.returncode == 1
    assert ("(last line: check broke; first: Diff in src/profiles.rs:521:)"
            in p.stderr), p.stderr


def test_an_existing_directory_is_refused(tmp_path):
    r, stub = repo(tmp_path)
    (tmp_path / "gates" / "g").mkdir(parents=True)
    p, _ = gate(r, stub, tmp_path)
    assert p.returncode == 2
    assert "exists (a gate never reuses a tree)" in p.stderr


def test_an_unknown_commit_is_refused(tmp_path):
    r, _ = repo(tmp_path)
    p = subprocess.run(["bash", str(GATE), "0" * 40], cwd=r, capture_output=True, text=True,
                       env=dict(os.environ, SCENSIM_GATE_ROOT=str(tmp_path / "gates")))
    assert p.returncode == 2 and "not a commit here" in p.stderr
