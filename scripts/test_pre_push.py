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
def test_check_pins_ignores_a_hooks_git_environment(monkeypatch):
    """As in a hook (GIT_DIR, GIT_INDEX_FILE set): the fixed commit still passes and the
    broken one still has its 4 mismatches."""
    import check_pins
    gd = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--absolute-git-dir"],
                        capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setenv("GIT_DIR", gd)
    monkeypatch.setenv("GIT_INDEX_FILE", gd + "/index")
    checked, bad = check_pins.check("ab7c7b82")
    if any("not in its checkout" in b for b in bad):
        pytest.skip("the component checkouts lack the commits")
    assert len(bad) == 4
    assert check_pins.check("494064bb")[1] == []


@pytest.mark.skipif(not _known("ab7c7b82", "494064bb"), reason="not this repository's history")
def test_it_would_have_refused_the_push_that_broke_main():
    import check_pins
    checked, bad = check_pins.check("ab7c7b82")
    if any("not in its checkout" in b for b in bad):
        pytest.skip("the component checkouts lack the commits")
    assert len(bad) == 4
    assert check_pins.check("494064bb")[1] == []


def _git(*args, cwd):
    return subprocess.run(["git", "-c", "protocol.file.allow=always", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


def _superproject(tmp_path):
    """A repository with one component submodule, and a worktree of it with the submodule
    checked out: the shape of every scensim worktree."""
    comp, sup = tmp_path / "component", tmp_path / "super"
    for d in (comp, sup):
        d.mkdir()
        _git("init", "-q", "-b", "main", cwd=d)
        _git("config", "user.email", "t@example.invalid", cwd=d)
        _git("config", "user.name", "t", cwd=d)
    (comp / "f").write_text("x\n")
    _git("add", "f", cwd=comp)
    _git("commit", "-qm", "c", cwd=comp)
    _git("submodule", "add", "-q", str(comp), "src/component", cwd=sup)
    _git("commit", "-qm", "pin", cwd=sup)
    wt = tmp_path / "wt"
    _git("worktree", "add", "-q", "--detach", str(wt), "main", cwd=sup)
    _git("submodule", "update", "-q", "--init", cwd=wt)
    return sup, wt, comp


def _push(wt, sha):
    """The hook as git runs it for a push from the worktree `wt`: at its top, with GIT_DIR (and
    GIT_INDEX_FILE) set to the worktree's, the push line on stdin."""
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")}
    env["GIT_DIR"] = _git("rev-parse", "--absolute-git-dir", cwd=wt)
    env["GIT_INDEX_FILE"] = env["GIT_DIR"] + "/index"
    return subprocess.run([sys.executable, str(ROOT / "scripts/hooks/pre-push"), "origin", "url"],
                          cwd=wt, env=env, input=f"refs/heads/x {sha} refs/heads/main {Z}\n",
                          capture_output=True, text=True)


def test_a_push_from_a_worktree_is_checked_against_its_submodules(tmp_path):
    """git runs a hook with GIT_DIR set; inherited by check_pins' `git -C <submodule>`, it read
    the superproject's repository and refused every push from a worktree as "pinned commit ...
    is not in its checkout" (5619e864, found by swb 243). The hook clears git's environment."""
    sup, wt, comp = _superproject(tmp_path)
    good = _git("rev-parse", "HEAD", cwd=wt)
    r = _push(wt, good)
    assert r.returncode == 0, r.stderr
    # still refused: a pin to a commit the worktree's component checkout does not have
    (comp / "f").write_text("y\n")
    _git("commit", "-qam", "c2", cwd=comp)
    _git("-C", "src/component", "fetch", "-q", "origin", cwd=sup)
    _git("-C", "src/component", "checkout", "-q", "origin/main", cwd=sup)
    _git("commit", "-qam", "pin c2", cwd=sup)
    r = _push(wt, _git("rev-parse", "main", cwd=sup))
    assert r.returncode == 1 and "is not in its checkout" in r.stderr


def test_the_installed_stub_runs_each_worktrees_hook_and_survives_a_removed_one(tmp_path):
    """install_hooks.sh puts a stub in the clone's shared hooks: a push from any worktree runs
    that worktree's scripts/hooks/pre-push, and removing the worktree it was installed from
    leaves it working (133); a hook of another origin is left alone."""
    import shutil
    sup, wt, comp = _superproject(tmp_path)
    for f in ("scripts/check_pins.py", "scripts/hooks/pre-push", "scripts/install_hooks.sh"):
        (sup / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, sup / f)
    _git("add", "scripts", cwd=sup)
    _git("commit", "-qm", "hooks", cwd=sup)
    for w in (wt, tmp_path / "wt2"):
        if w.exists():
            _git("checkout", "-q", "--detach", "main", cwd=w)
        else:
            _git("worktree", "add", "-q", "--detach", str(w), "main", cwd=sup)
        _git("submodule", "update", "-q", "--init", cwd=w)
    subprocess.run(["bash", str(tmp_path / "wt2/scripts/install_hooks.sh")], check=True,
                   capture_output=True)
    _git("worktree", "remove", "--force", str(tmp_path / "wt2"), cwd=sup)
    stub = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=wt)) / \
        "hooks" / "pre-push"
    assert "scensim install-hooks stub" in stub.read_text()

    def push(sha):
        env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")}
        env["GIT_DIR"] = _git("rev-parse", "--absolute-git-dir", cwd=wt)
        env["GIT_INDEX_FILE"] = env["GIT_DIR"] + "/index"
        return subprocess.run([str(stub), "origin", "url"], cwd=wt, env=env,
                              input=f"refs/heads/x {sha} refs/heads/main {Z}\n",
                              capture_output=True, text=True)

    assert push(_git("rev-parse", "HEAD", cwd=wt)).returncode == 0
    (comp / "f").write_text("y\n")
    _git("commit", "-qam", "c2", cwd=comp)
    _git("-C", "src/component", "fetch", "-q", "origin", cwd=sup)
    _git("-C", "src/component", "checkout", "-q", "origin/main", cwd=sup)
    _git("commit", "-qam", "pin c2", cwd=sup)
    r = push(_git("rev-parse", "main", cwd=sup))
    assert r.returncode == 1 and "is not in its checkout" in r.stderr
    # a checkout from before the hook: a push to main is refused, any other ref goes (243)
    _git("checkout", "-q", "--detach", "main~2", cwd=wt)   # "pin": before "hooks"
    assert not (wt / "scripts/hooks/pre-push").exists()
    r = push(_git("rev-parse", "main", cwd=sup))
    assert r.returncode == 1 and "cannot be checked" in r.stderr
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")}
    r = subprocess.run([str(stub), "origin", "url"], cwd=wt, env=env, capture_output=True,
                       text=True, input=f"refs/heads/x {'a' * 40} refs/heads/feature {Z}\n")
    assert r.returncode == 0, r.stderr
    _git("checkout", "-q", "--detach", "main", cwd=wt)
    # a foreign hook is left alone
    stub.write_text("#!/bin/sh\nexit 0\n")
    out = subprocess.run(["bash", str(wt / "scripts/install_hooks.sh")], capture_output=True,
                         text=True)
    assert "left alone" in out.stderr and stub.read_text() == "#!/bin/sh\nexit 0\n"


def test_an_uninitialised_submodule_refuses_the_push_by_name(tmp_path):
    """Issue 101: check_pins took its components from the checkouts that exist, so a worktree
    with a submodule not initialised (scensim_carla_world, acb) passed with its deps/ pins
    unread. It is refused now, by name."""
    sup, wt, comp = _superproject(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    _git("init", "-q", "-b", "main", cwd=other)
    _git("config", "user.email", "t@example.invalid", cwd=other)
    _git("config", "user.name", "t", cwd=other)
    (other / "g").write_text("x\n")
    _git("add", "g", cwd=other)
    _git("commit", "-qm", "o", cwd=other)
    _git("submodule", "add", "-q", str(other), "src/other", cwd=sup)
    _git("commit", "-qm", "pin other", cwd=sup)
    sha = _git("rev-parse", "main", cwd=sup)
    _git("checkout", "-q", "--detach", sha, cwd=wt)
    _git("submodule", "update", "-q", "--init", "src/component", cwd=wt)   # src/other left out
    r = _push(wt, sha)
    assert r.returncode == 1 and "src/other: not initialised" in r.stderr, r.stderr
    _git("submodule", "update", "-q", "--init", "src/other", cwd=wt)
    r = _push(wt, sha)
    assert r.returncode == 0, r.stderr
