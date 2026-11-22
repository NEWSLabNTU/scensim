#!/usr/bin/env python3
"""The pin check (roadmap 051): every component builds against the commits this workspace pins.

A component repository carries its own dependencies as submodules under `deps/`, so that it
builds on its own (decision 4). Here, where the same repositories are direct submodules, its
`deps/<repo>` pin must be the commit this repository pins for that repository: otherwise the
component is built and tested against other code than its neighbours. Repositories are
matched by URL. Reads the pins from git (the committed tree), not from checkouts.

    scripts/check_pins.py              exit 1 on a mismatch, naming component, dependency and both commits
    scripts/check_pins.py --rev <sha>  the same for another commit of this repository (the pre-push
                                       hook's: the commit a push to main would make main)
"""

import argparse
import configparser
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*args, **kw):
    """git, without the environment of a hook that runs this: git sets GIT_DIR (and
    GIT_INDEX_FILE, in a worktree more) for its hooks, and a `git -C <submodule>` that inherits
    them reads the superproject's repository instead (5619e864's pre-push hook refused every
    push from a worktree)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], env=env, capture_output=True, text=True, **kw)


def submodules(repo, rev="HEAD"):
    """{url: (path, commit)} of `repo`'s submodules at `rev`."""
    try:
        text = _git("-C", str(repo), "show", f"{rev}:.gitmodules", check=True).stdout
    except subprocess.CalledProcessError:
        return {}
    cfg = configparser.ConfigParser()
    cfg.read_string(text)
    out = {}
    for section in cfg.sections():
        path, url = cfg[section]["path"], cfg[section]["url"]
        tree = _git("-C", str(repo), "ls-tree", rev, path, check=True).stdout.split()
        if len(tree) >= 3 and tree[1] == "commit":
            out[url.removesuffix(".git").rstrip("/")] = (path, tree[2])
    return out


def check(rev="HEAD", root=ROOT):
    """(dependencies checked, [mismatch lines]) of `root` at commit `rev`."""
    ours = submodules(root, rev)
    bad, checked = [], 0
    for url, (path, commit) in sorted(ours.items()):
        component = root / path
        if not (component / ".git").exists():
            # an uninitialised submodule's deps/ pins cannot be read, and skipping it passed a
            # tree with scensim_carla_world and acb not checked out at all (issue 101)
            bad.append(f"{path}: not initialised, so its deps/ pins cannot be checked: "
                       f"`git submodule update --init --recursive {path}`, then run this again")
            continue
        known = _git("-C", str(component), "cat-file", "-e",
                     f"{commit}^{{commit}}").returncode == 0
        if not known:
            # Without the commit its deps/ pins cannot be read; skipping it silently once
            # reported "0 checked, 0 mismatches" over three real mismatches (roadmap 070).
            bad.append(f"{path}: pinned commit {commit[:10]} is not in its checkout: "
                       f"`git -C {path} fetch origin`, then run this again")
            continue
        for dep_url, (dep_path, dep_commit) in submodules(component, commit).items():
            if not dep_path.startswith("deps/"):
                continue
            checked += 1
            mine = ours.get(dep_url)
            if mine is None:
                bad.append(f"{path}/{dep_path}: {dep_url} is not a submodule here")
            elif mine[1] != dep_commit:
                bad.append(f"{path}/{dep_path} is {dep_commit[:10]}, but {mine[0]} here is "
                           f"{mine[1][:10]}: move one pin to the other")
    if any(": not initialised" in b for b in bad):
        bad.append("every submodule must be initialised to check the pins: "
                   "`git submodule update --init --recursive` initialises the whole set at once")
    return checked, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="every component's deps/ pins are this workspace's")
    ap.add_argument("--rev", default="HEAD", help="the commit of this repository to check")
    a = ap.parse_args(argv)
    checked, bad = check(a.rev)
    for line in bad:
        print(f"FAIL: {line}")
    print(f"pins: {checked} component dependencies checked, {len(bad)} mismatch(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
