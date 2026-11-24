"""check_release_rosdep.py (issue 146): a workspace dependency outside the rosdep step's paths
is named, with who depends on it; one inside, a deps/ copy behind COLCON_IGNORE, a dependency
on a rosdistro package and one whose condition is false are not."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_release_rosdep as crr  # noqa: E402

WORKFLOW = """\
env:
  SIM: >-
    src/a
jobs:
  build-sim:
    steps:
      - name: rosdep
        run: |
          rosdep install --from-paths $SIM \\
            src/b /tmp/vendor --ignore-src -y -q
"""


def package(root, rel, name, deps=()):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(f"<exec_depend{c}>{n}</exec_depend>" for n, c in deps)
    (d / "package.xml").write_text(
        f'<?xml version="1.0"?><package format="3"><name>{name}</name><version>0.0.0</version>'
        f'<description>x</description><maintainer email="x@example.com">x</maintainer><license>x</license>'
        f"{body}</package>")


def tree(tmp_path, deps):
    package(tmp_path, "src/a", "a", deps)
    package(tmp_path, "src/b", "b")
    package(tmp_path, "src/c", "c")
    # a component's deps/ copy of c: rosdep (catkin_pkg) skips it
    package(tmp_path, "src/b/deps/c", "c")
    (tmp_path / "src/b/deps/COLCON_IGNORE").write_text("")
    wf = tmp_path / "release.yml"
    wf.write_text(WORKFLOW)
    return wf


def test_the_step_paths_are_read_with_the_workflow_env(tmp_path):
    assert crr.rosdep_paths(tree(tmp_path, [])) == ["src/a", "src/b"]


def test_a_dependency_outside_the_paths_is_named(tmp_path, capsys):
    wf = tree(tmp_path, [("c", ""), ("b", ""), ("rclpy", "")])
    assert crr.check(tmp_path, crr.rosdep_paths(wf)) == [("c", "src/c", ["a"])]
    assert crr.main(["--root", str(tmp_path), "--workflow", str(wf)]) == 1
    assert "c (src/c) is not under the step's paths, and a depend(s) on it" in capsys.readouterr().err


def test_inside_the_paths_or_conditioned_out_passes(tmp_path):
    wf = tree(tmp_path, [("b", ""), ("c", ' condition="$ROS_VERSION == 1"')])
    assert crr.check(tmp_path, crr.rosdep_paths(wf)) == []
    assert crr.main(["--root", str(tmp_path), "--workflow", str(wf)]) == 0
