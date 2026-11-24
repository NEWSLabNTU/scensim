#!/usr/bin/env python3
"""release.yml's rosdep step reads every workspace package its packages depend on (issue 146).

`rosdep install --from-paths <paths> --ignore-src` skips a dependency only when the package it
names is found under <paths>; a dependency on one of this workspace's packages that lies
elsewhere is looked up in rosdistro, is not there, and the step fails ("Cannot locate rosdep
definition for [scensim_sampler]"). That is what broke the release's build-sim after 092 K3 gave
`scensim` an exec_depend on `scensim_sampler` without adding `src/scensim_sampler` to the step.

    python3 scripts/check_release_rosdep.py [--root <repo>] [--workflow <release.yml>]

Finds packages as rosdep does (catkin_pkg: a COLCON_IGNORE, CATKIN_IGNORE or AMENT_IGNORE
directory is skipped, so the components' deps/ copies are not counted) and reads every
dependency type rosdep installs, conditions evaluated for ROS 2. Exits 1 naming each missing
package and who depends on it; 0 otherwise.
"""
import argparse
import os
import re
import shlex
import sys
from pathlib import Path

import yaml
from catkin_pkg.packages import find_packages

DEP_FIELDS = ("build_depends", "buildtool_depends", "build_export_depends", "buildtool_export_depends",
              "exec_depends", "test_depends", "doc_depends")


def rosdep_paths(workflow):
    """The `--from-paths` arguments of the build-sim job's rosdep step, the workflow's env
    variables expanded; paths outside the repository (the vendored sim.repos) left out."""
    doc = yaml.safe_load(Path(workflow).read_text())
    env = {k: " ".join(str(v).split()) for k, v in (doc.get("env") or {}).items()}
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            run = step.get("run") or ""
            m = re.search(r"rosdep install --from-paths (.*?) --ignore-src", run.replace("\\\n", " "),
                          re.S)
            if step.get("name") == "rosdep" and m:
                words = shlex.split(re.sub(r"\$(\w+)|\$\{(\w+)\}",
                                           lambda v: env.get(v[1] or v[2], ""), m[1]))
                return [w for w in words if not w.startswith("/")]
    raise SystemExit(f"{workflow}: no step named rosdep with `rosdep install --from-paths ... "
                     "--ignore-src`")


def packages(root):
    """name -> path (relative to root) for every package rosdep would find under src/."""
    return {p.name: f"src/{Path(path).as_posix()}"
            for path, p in find_packages(str(Path(root) / "src")).items()}


def check(root, paths):
    """[(missing package, its path, [packages depending on it])]."""
    env = dict(os.environ, ROS_VERSION="2")
    found = {}
    for rel in paths:
        for path, pkg in find_packages(str(Path(root) / rel)).items():
            found[pkg.name] = (Path(rel) / path).as_posix()
    workspace = packages(root)
    readers = {}
    for rel in paths:
        for pkg in find_packages(str(Path(root) / rel)).values():
            pkg.evaluate_conditions(env)
            for field in DEP_FIELDS:
                for dep in getattr(pkg, field):
                    if dep.evaluated_condition is False:
                        continue
                    if dep.name in workspace and dep.name not in found:
                        readers.setdefault(dep.name, set()).add(pkg.name)
    return [(name, workspace[name], sorted(who)) for name, who in sorted(readers.items())]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    here = Path(__file__).resolve().parent.parent
    ap.add_argument("--root", default=str(here))
    ap.add_argument("--workflow", default=None)
    a = ap.parse_args(argv)
    workflow = a.workflow or str(Path(a.root) / ".github/workflows/release.yml")
    paths = rosdep_paths(workflow)
    missing = check(a.root, paths)
    for name, path, who in missing:
        print(f"release.yml rosdep: {name} ({path}) is not under the step's paths, and "
              f"{', '.join(who)} depend(s) on it: add {path} to the step", file=sys.stderr)
    if missing:
        return 1
    print(f"release.yml rosdep: {len(paths)} paths, every workspace dependency under them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
