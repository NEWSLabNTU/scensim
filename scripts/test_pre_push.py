"""The pre-push hook (scripts/hooks/pre-push): which pushes it checks, that it refuses one whose
pins do not match, and, where this repository's history and checkouts have it, the push that
broke main (ab7c7b82, a docs edit whose -a commit reverted five pins)."""
import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.dont_write_bytecode = True     # no __pycache__ beside the hook (install-hooks links files)
loader = importlib.machinery.SourceFileLoader("pre_push", str(ROOT / "scripts/hooks/pre-push"))
spec = importlib.util.spec_from_loader("pre_push", loader)
hook = importlib.util.module_from_spec(spec)
loader.exec_module(hook)

A, B, Z = "a" * 40, "b" * 40, "0" * 40


def test_only_pushes_to_main_are_checked():
    lines = [f"refs/heads/x {A} refs/heads/main {B}",
             f"refs/heads/y {B} refs/heads/feature {A}",
             f"(delete) {Z} refs/heads/main {A}",
             "garbage"]
    assert hook.targets(lines) == [("refs/heads/main", A)]


def test_a_mismatch_refuses_the_push(capsys):
    lines = [f"refs/heads/x {A} refs/heads/main {B}"]
    assert hook.run(lines, lambda sha: (10, [])) == 0
    assert hook.run(lines, lambda sha: (10, ["src/c/deps/d is 1, but src/d here is 2"])) == 1
    err = capsys.readouterr().err
    assert "refusing to push aaaaaaaaaa to refs/heads/main" in err and "src/c/deps/d" in err
    assert hook.run([f"refs/heads/x {A} refs/heads/feature {B}"],
                    lambda sha: (10, ["bad"])) == 0          # not main: not checked


def _known(*commits):
    return all(subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{c}^{{commit}}"],
                              capture_output=True).returncode == 0 for c in commits)


@pytest.mark.skipif(not _known("ab7c7b82", "494064bb"), reason="not this repository's history")
def test_it_would_have_refused_the_push_that_broke_main():
    import check_pins
    checked, bad = check_pins.check("ab7c7b82")
    if any("not in its checkout" in b for b in bad):
        pytest.skip("the component checkouts lack the commits")
    assert len(bad) == 4
    assert check_pins.check("494064bb")[1] == []
