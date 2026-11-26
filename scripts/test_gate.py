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
echo "stub env: MAKEFLAGS=${MAKEFLAGS:-} CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS:-} COLCON_DEFAULTS_FILE=${COLCON_DEFAULTS_FILE:-} PWD=$PWD"
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


def gate(r, stub, tmp_path, dirname="g", isaac=None, host=None, **stub_env):
    # the stub's own settings reach it through the clean environment's only door: a wrapper
    wrapper = tmp_path / f"just-{dirname}"
    exports = "".join(f"export {k}={v}\n" for k, v in stub_env.items())
    wrapper.write_text(f"#!/bin/bash\n{exports}exec {stub} \"$@\"\n")
    wrapper.chmod(0o755)
    carry = ("ISAAC_ROOT", "SCENSIM_BUILD_JOBS", "MAKEFLAGS", "CARGO_BUILD_JOBS",
             "COLCON_DEFAULTS_FILE", "CUDA_VISIBLE_DEVICES", "GATE_WRAP")
    env = {k: v for k, v in os.environ.items() if k not in carry}
    env.update(host or {})
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


def test_the_gate_carries_the_hosts_settings_and_names_them(tmp_path):
    """118's gap: .env and an allow-list of the caller's host settings reach the steps."""
    r, stub = repo(tmp_path)
    (r / ".env").write_text("SCENSIM_GATE_TEST=1\n")
    p, d = gate(r, stub, tmp_path, host={"MAKEFLAGS": "-j3", "CARGO_BUILD_JOBS": "4",
                                         "COLCON_DEFAULTS_FILE": "/c.yaml",
                                         "SOMETHING_ELSE": "x"})
    assert p.returncode == 0, p.stderr
    assert (d / ".env").read_text() == "SCENSIM_GATE_TEST=1\n"
    log = (d / "gate.log").read_text()
    assert "stub env: MAKEFLAGS=-j3 CARGO_BUILD_JOBS=4 COLCON_DEFAULTS_FILE=/c.yaml" in log
    assert "SOMETHING_ELSE" not in log
    line = p.stdout.strip().splitlines()[-1]
    assert line.endswith("; carried .env MAKEFLAGS CARGO_BUILD_JOBS COLCON_DEFAULTS_FILE"), line


def test_gate_wrap_runs_every_step_under_it(tmp_path):
    r, stub = repo(tmp_path)
    wrap = tmp_path / "wrap.sh"
    marks = tmp_path / "wrapped.txt"
    wrap.write_text(f"#!/bin/bash\necho \"$*\" >> {marks}\nexec \"$@\"\n")
    wrap.chmod(0o755)
    p, _ = gate(r, stub, tmp_path, host={"GATE_WRAP": str(wrap)})
    assert p.returncode == 0, p.stderr
    assert [ln.split()[-1] for ln in marks.read_text().splitlines()] == ["build", "test", "check"]
    assert p.stdout.strip().splitlines()[-1].endswith(f"; carried nothing; under {wrap}")


# --- scripts/gate_clean.sh: a landed gate's worktree goes, a rebased one's SHA is tagged ----

CLEAN = Path(__file__).resolve().parent / "gate_clean.sh"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def git(r, *a):
    return subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True,
                          text=True, env=ENV).stdout.strip()


def commit(r, name, text):
    (r / name).write_text(text)
    git(r, "add", name)
    git(r, "commit", "-qm", name)
    return git(r, "rev-parse", "HEAD")


def landed_repo(tmp_path):
    """A clone of a bare origin with one commit on main, and a gate worktree root."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    r = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(r)], check=True,
                   capture_output=True)
    git(r, "checkout", "-q", "-b", "main")
    commit(r, "a.txt", "a\n")
    git(r, "push", "-q", "origin", "main")
    return r, tmp_path / "gates"


def gate_tree(r, root, sha):
    d = root / f"gate-{sha[:8]}"
    git(r, "worktree", "add", "-q", "--detach", str(d), sha)
    return d


def clean(r, root, sha, *extra):
    return subprocess.run(["bash", str(CLEAN), sha, *extra], cwd=r, capture_output=True,
                          text=True, env=dict(ENV, SCENSIM_GATE_ROOT=str(root)))


def test_gate_clean_removes_a_worktree_whose_commit_is_on_origin(tmp_path):
    r, root = landed_repo(tmp_path)
    sha = commit(r, "b.txt", "b\n")
    d = gate_tree(r, root, sha)
    git(r, "push", "-q", "origin", "main")
    p = clean(r, root, sha)
    assert p.returncode == 0, p.stdout + p.stderr
    assert not d.exists() and "tag gate/" not in p.stdout    # (the echo names notag:=)
    assert git(r, "tag", "-l") == ""


def rebased_gate(tmp_path):
    r, root = landed_repo(tmp_path)
    git(r, "checkout", "-q", "-b", "topic")
    sha = commit(r, "b.txt", "b\n")
    d = gate_tree(r, root, sha)
    git(r, "checkout", "-q", "main")
    commit(r, "c.txt", "c\n")
    git(r, "push", "-q", "origin", "main")
    git(r, "checkout", "-q", "topic")
    git(r, "rebase", "-q", "main")
    git(r, "push", "-q", "origin", "topic:main")
    git(r, "checkout", "-q", "main")
    git(r, "branch", "-q", "-f", "topic", "main")
    return r, root, sha, d


def test_gate_clean_notag_keeps_a_rebased_gate_and_prints_the_tag_command(tmp_path):
    """118's user gives their own go for every tag: notag never tags."""
    r, root, sha, d = rebased_gate(tmp_path)
    p = clean(r, root, sha, "notag:=true")
    assert p.returncode == 1, p.stdout + p.stderr
    assert d.exists() and git(r, "tag", "-l") == ""
    assert f"  git tag gate/gate-{sha[:8]} {sha} && just gate-clean {sha}" in p.stdout


def test_gate_clean_notag_still_removes_a_gate_on_origin(tmp_path):
    r, root = landed_repo(tmp_path)
    sha = commit(r, "b.txt", "b\n")
    d = gate_tree(r, root, sha)
    git(r, "push", "-q", "origin", "main")
    p = clean(r, root, sha, "notag:=true")
    assert p.returncode == 0 and not d.exists(), p.stdout + p.stderr


def test_gate_clean_tags_a_gate_that_landed_rebased(tmp_path):
    r, root = landed_repo(tmp_path)
    git(r, "checkout", "-q", "-b", "topic")
    sha = commit(r, "b.txt", "b\n")
    d = gate_tree(r, root, sha)
    git(r, "checkout", "-q", "main")
    commit(r, "c.txt", "c\n")                         # main moved while the gate ran
    git(r, "push", "-q", "origin", "main")
    git(r, "checkout", "-q", "topic")
    git(r, "rebase", "-q", "main")                    # the rebased commit is what lands
    git(r, "push", "-q", "origin", "topic:main")
    git(r, "checkout", "-q", "main")
    git(r, "branch", "-q", "-f", "topic", "main")     # nothing local holds the gated SHA
    p = clean(r, root, sha)
    assert p.returncode == 0, p.stdout + p.stderr
    tag = f"gate/gate-{sha[:8]}"
    assert f"tag {tag} -> {sha}" in p.stdout
    assert git(r, "rev-parse", f"{tag}^{{commit}}") == sha
    assert not d.exists()


def test_gate_clean_keeps_a_gate_whose_commit_has_not_landed(tmp_path):
    r, root = landed_repo(tmp_path)
    sha = commit(r, "b.txt", "b\n")
    d = gate_tree(r, root, sha)
    p = clean(r, root, sha)
    assert p.returncode == 1 and "kept" in p.stdout
    assert d.exists() and git(r, "tag", "-l") == ""


def test_gate_clean_keeps_a_worktree_with_tracked_changes(tmp_path):
    r, root = landed_repo(tmp_path)
    sha = commit(r, "b.txt", "b\n")
    git(r, "push", "-q", "origin", "main")
    d = gate_tree(r, root, sha)
    (d / "b.txt").write_text("changed\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "has tracked changes: kept" in p.stdout
    assert d.exists()


# --- gate_clean.sh after an interrupted checkout, and --dir (issue 191's fifth follow-up) ----

def git_f(r, *a):
    """git with file:// submodules allowed (a test's local origins)."""
    return git(r, "-c", "protocol.file.allow=always", *a)


def repo_with_submodule(tmp_path):
    """A superproject on a bare origin pinning one submodule (two files) on its own origin."""
    sub_origin = tmp_path / "sub.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(sub_origin)], check=True)
    s = tmp_path / "subwork"
    subprocess.run(["git", "clone", "-q", str(sub_origin), str(s)], check=True,
                   capture_output=True)
    git(s, "checkout", "-q", "-b", "main")
    commit(s, "one.txt", "1\n")
    commit(s, "two.txt", "2\n")
    git(s, "push", "-q", "origin", "main")
    r, root = landed_repo(tmp_path)
    git_f(r, "submodule", "add", "-q", str(sub_origin), "sub")
    git(r, "commit", "-qm", "sub")
    git(r, "push", "-q", "origin", "main")
    return r, root, git(r, "rev-parse", "HEAD")


def sub_gate(r, root, sha, name=None):
    d = root / (name or f"gate-{sha[:8]}")
    git(r, "worktree", "add", "-q", "--detach", str(d), sha)
    git_f(d, "submodule", "update", "-q", "--init", "--recursive")
    return d


def test_gate_clean_removes_a_gate_whose_submodule_checkout_was_cut_short(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha)
    (d / "sub" / "one.txt").unlink()
    (d / "sub" / "two.txt").unlink()                   # a clone stopped before its checkout
    p = clean(r, root, sha)
    assert p.returncode == 0, p.stdout + p.stderr
    pin = git(r, "ls-tree", sha, "sub").split()[2]
    assert f"sub: an interrupted checkout at {pin[:8]}, 2 files missing" in p.stdout
    assert not d.exists()


def test_gate_clean_keeps_a_submodule_with_an_edit(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha)
    (d / "sub" / "one.txt").unlink()
    (d / "sub" / "two.txt").write_text("edited\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "sub/two.txt: a tracked change ( M): kept" in p.stdout
    assert d.exists()


def test_gate_clean_keeps_a_submodule_at_another_commit(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha)
    commit(d / "sub", "three.txt", "3\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "not its pin" in p.stdout and d.exists()


def test_gate_clean_keeps_a_superprojects_own_change(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha)
    (d / "a.txt").write_text("changed\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "a.txt: a tracked change ( M): kept" in p.stdout
    assert d.exists()


def test_gate_clean_dir_removes_a_custom_named_gate(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha, name=f"gate-{sha[:8]}-2")
    assert clean(r, root, sha).returncode == 1          # not at the default path
    p = clean(r, root, sha, f"dir:={d}")
    assert p.returncode == 0, p.stdout + p.stderr
    assert not d.exists()


def test_gate_clean_dir_refuses_a_worktree_at_another_commit(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    first = git(r, "rev-parse", "HEAD~1")
    d = sub_gate(r, root, first, name="gate-other")
    p = clean(r, root, sha, f"dir:={d}")
    assert p.returncode == 1 and f"not {sha}: refused" in p.stdout and d.exists()


def test_gate_clean_dir_refuses_a_directory_that_is_no_worktree(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    stray = tmp_path / "stray"
    stray.mkdir()
    (stray / "keep.txt").write_text("mine\n")
    p = clean(r, root, sha, f"dir:={stray}")
    assert p.returncode == 1 and "is not a worktree of this repository: refused" in p.stdout
    assert (stray / "keep.txt").read_text() == "mine\n"


# --- gate_clean.sh: a gate stopped early, and an unlanded gate (issue 191's sixth follow-up) --

def bare_with(tmp_path, name, files, sub=None):
    """A bare origin `name`.git whose main holds `files` (and `sub`, an origin, at deps/inner)."""
    origin = tmp_path / f"{name}.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    w = tmp_path / f"{name}work"
    subprocess.run(["git", "clone", "-q", str(origin), str(w)], check=True, capture_output=True)
    git(w, "checkout", "-q", "-b", "main")
    for f in files:
        commit(w, f, f + "\n")
    if sub:
        git_f(w, "submodule", "add", "-q", str(sub), "deps/inner")
        git(w, "commit", "-qm", "inner")
    git(w, "push", "-q", "origin", "main")
    return origin, w


def repo_with_nested(tmp_path):
    """A superproject pinning `mid`, which pins its own submodule deps/inner (as acb does)."""
    inner, _ = bare_with(tmp_path, "inner", ["x.txt"])
    mid, _ = bare_with(tmp_path, "mid", [".envrc", "m.txt"], sub=inner)
    r, root = landed_repo(tmp_path)
    git_f(r, "submodule", "add", "-q", str(mid), "mid")
    git(r, "commit", "-qm", "mid")
    git(r, "push", "-q", "origin", "main")
    return r, root, git(r, "rev-parse", "HEAD")


def empty_index(sub, *gone):
    """A checkout stopped after its clone wrote HEAD: no index, and `gone` not on disk."""
    (Path(git(sub, "rev-parse", "--absolute-git-dir")) / "index").unlink()
    for f in gone:
        (sub / f).unlink()


def test_gate_clean_removes_a_nested_submodule_whose_checkout_was_cut_short(tmp_path):
    r, root, sha = repo_with_nested(tmp_path)
    d = sub_gate(r, root, sha)
    empty_index(d / "mid", ".envrc", "m.txt")
    p = clean(r, root, sha)
    assert p.returncode == 0, p.stdout + p.stderr
    pin = git(r, "ls-tree", sha, "mid").split()[2]
    assert f"mid: an interrupted checkout at {pin[:8]}" in p.stdout
    assert not d.exists()


def test_gate_clean_keeps_a_nested_submodule_with_an_edit(tmp_path):
    r, root, sha = repo_with_nested(tmp_path)
    d = sub_gate(r, root, sha)
    (d / "mid" / "m.txt").write_text("edited\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "mid/m.txt: a tracked change ( M): kept" in p.stdout
    assert d.exists()


def test_gate_clean_removes_a_submodule_left_on_its_clones_branch(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    s = tmp_path / "subwork"
    commit(s, "three.txt", "3\n")                    # the origin moves on past the pin
    git(s, "push", "-q", "origin", "main")
    d = sub_gate(r, root, sha)
    git_f(d / "sub", "fetch", "-q", "origin")
    git(d / "sub", "checkout", "-q", "origin/main")   # where a clone stands before its pin
    p = clean(r, root, sha)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "sub: an interrupted checkout" in p.stdout and "on origin" in p.stdout
    assert not d.exists()


def test_gate_clean_still_keeps_a_submodule_at_a_local_commit(tmp_path):
    r, root, sha = repo_with_submodule(tmp_path)
    d = sub_gate(r, root, sha)
    commit(d / "sub", "three.txt", "3\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "not its pin" in p.stdout and d.exists()


def unlanded_gate(tmp_path, keep_branch):
    r, root = landed_repo(tmp_path)
    git(r, "checkout", "-q", "-b", "topic")
    sha = commit(r, "b.txt", "b\n")
    git(r, "checkout", "-q", "main")
    if not keep_branch:
        git(r, "branch", "-q", "-D", "topic")
    return r, root, sha, gate_tree(r, root, sha)


def test_gate_clean_unlanded_removes_a_gate_whose_sha_a_branch_keeps(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    p = clean(r, root, sha, "unlanded:=true")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "refs/heads/topic" in p.stdout and not d.exists()
    assert git(r, "tag", "-l") == ""


def test_gate_clean_unlanded_keeps_a_gate_whose_sha_only_it_holds(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=False)
    p = clean(r, root, sha, "unlanded:=true")
    assert p.returncode == 1 and "no local branch or tag" in p.stdout and d.exists()


def test_gate_clean_without_unlanded_names_the_flag(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    p = clean(r, root, sha)
    assert p.returncode == 1 and "unlanded:=true" in p.stdout and d.exists()


def test_gate_clean_keeps_a_branch_head_submodule_with_an_untracked_file(tmp_path):
    # 133's condition (a): on its clone's branch, only deletions count as interrupted
    r, root, sha = repo_with_submodule(tmp_path)
    s = tmp_path / "subwork"
    commit(s, "three.txt", "3\n")
    git(s, "push", "-q", "origin", "main")
    d = sub_gate(r, root, sha)
    git_f(d / "sub", "fetch", "-q", "origin")
    git(d / "sub", "checkout", "-q", "origin/main")
    (d / "sub" / "one.txt").unlink()
    (d / "sub" / "mine.txt").write_text("someone's\n")
    p = clean(r, root, sha)
    assert p.returncode == 1 and "sub/mine.txt: untracked: kept" in p.stdout and d.exists()


def test_gate_clean_unlanded_does_not_count_a_gate_tag(tmp_path):
    # 133's condition (c): gate-clean's own gate/* tags never make an unlanded SHA safe
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=False)
    git(r, "tag", f"gate/gate-{sha[:8]}", sha)
    p = clean(r, root, sha, "unlanded:=true")
    assert p.returncode == 1 and "no local branch or tag" in p.stdout and d.exists()


# --- gate-clean's arguments by name, through the recipe (issue 191's seventh follow-up) -----

JUSTFILE = Path(__file__).resolve().parent.parent / "justfile"


def just_clean(r, root, sha, *args):
    """`just gate-clean` as a user types it, run against the test's repository."""
    return subprocess.run(["just", "--justfile", str(JUSTFILE), "--working-directory", str(r),
                           "gate-clean", sha, *args], cwd=r, capture_output=True, text=True,
                          env=dict(ENV, SCENSIM_GATE_ROOT=str(root)))


def test_recipe_unlanded_by_name_removes_the_gate(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    p = just_clean(r, root, sha, "unlanded:=true")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "kept by refs/heads/topic" in p.stdout and not d.exists()


def test_recipe_notag_by_name_tags_nothing(tmp_path):
    r, root, sha, d = rebased_gate(tmp_path)
    p = just_clean(r, root, sha, "notag:=true")
    assert p.returncode == 1, p.stdout + p.stderr
    assert "notag:=true" in p.stdout and d.exists() and git(r, "tag", "-l") == ""


def refused(r, root, sha, d, arg, *want):
    p = clean(r, root, sha, arg)
    assert p.returncode == 2, p.stdout + p.stderr
    for w in want:
        assert w in p.stdout + p.stderr, p.stdout + p.stderr
    assert d.exists() and git(r, "tag", "-l") == ""


def test_a_bare_name_value_is_refused_naming_the_form(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    refused(r, root, sha, d, "unlanded=true", "unlanded:=true")


def test_an_old_flag_is_refused_naming_its_new_form(tmp_path):
    r, root, sha, d = rebased_gate(tmp_path)
    refused(r, root, sha, d, "--notag", "notag:=true")


def test_an_unknown_name_is_refused(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    refused(r, root, sha, d, "foo:=1", "unknown argument 'foo:=1'", "unlanded:=")


def test_a_bad_value_is_refused(tmp_path):
    r, root, sha, d = rebased_gate(tmp_path)
    refused(r, root, sha, d, "notag:=yes", "notag:=true or notag:=false")


def test_an_empty_dir_is_refused(tmp_path):
    r, root, sha, d = unlanded_gate(tmp_path, keep_branch=True)
    refused(r, root, sha, d, "dir:=", "dir:= needs a path")
