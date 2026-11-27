"""Issue 195: no truth or scenario pose reaches an autopilot's localization, except through one
opt-in debug option, `direct_localization`, whose runs are marked so they cannot pass as an
evaluation."""

import pytest
import yaml

from scensim import run, stack, world
from scensim.results import ResultError, RunResult

from test_project import make, scenario_checks, whats


def tb(pilot: str, simulator: str = "carla") -> str:
    return f"simulator: {simulator}\nassets: []\npilots:\n  ego: {pilot}\n"


# --- the option and the retired arguments ------------------------------------------------------

def test_direct_localization_is_a_pilot_key(host):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, autoware_profile: scensim, "
                             "direct_localization: true}"))
    assert scenario_checks(d) == []


def test_direct_localization_is_true_or_false(host):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, autoware_profile: scensim, "
                             "direct_localization: yes please}"))
    assert any("direct_localization" in w and "true or false" in w
               for w in whats(scenario_checks(d)))


def test_direct_localization_on_the_stock_profile_names_the_one_that_has_it(host):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, direct_localization: true}"))
    [f] = [f for f in scenario_checks(d) if "direct_localization" in f.what]
    assert "autoware_profile: scensim" in f.fix and "ndt:=none" in f.what


def test_any_other_pilot_kind_may_use_it(host):
    d = make(host["tmp"], tb("{kind: launch, launch: my_pkg my.launch.xml, vehicle: tesla_model3, "
                             "direct_localization: true}"))
    assert not [f for f in scenario_checks(d) if "direct_localization" in f.what]


@pytest.mark.parametrize("arg,names", [
    ("seed_localization_on_attach", "retired"),
    ("publish_direct_localization", "direct_localization: true"),
    ("truth_pose_estimate", "direct_localization: true"),
])
def test_the_truth_knobs_are_refused_as_pilot_args(host, arg, names):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, autoware_profile: scensim, "
                             f"args: {{{arg}: true}}}}"))
    hits = [f for f in scenario_checks(d) if arg in f.what]
    assert hits and any(names in (f.what + " " + (f.fix or "")) for f in hits)


# --- Isaac: the ego config -------------------------------------------------------------------

def test_the_isaac_ego_config_publishes_the_truth_as_the_pose_estimate(tmp_path):
    base = tmp_path / "ego.yaml"
    base.write_text("rig: tesla_model3.rig.yaml\ndomain: 1\n")
    doc = stack.isaac_ego_with_ground_truth(base, pose_estimate=True)
    assert doc["ground_truth"]["pose_estimate"] is True
    assert stack.isaac_ego_with_ground_truth(base)["ground_truth"].get("pose_estimate") in (
        None, False)


def test_a_users_ego_config_cannot_turn_the_truth_on_itself(tmp_path):
    ego = tmp_path / "my_ego.yaml"
    ego.write_text(yaml.safe_dump({"rig": "x.rig.yaml", "ground_truth": {"pose_estimate": True}}))
    out = world.problems({"isaac": {"ego": str(ego)}}, "isaac", tmp_path)
    assert any(k == "isaac.ego" and "direct_localization" in m for k, m in out)


# --- the debug mark ----------------------------------------------------------------------------

def test_the_result_carries_the_debug_options():
    r = RunResult("r", "passed", debug=["direct_localization"])
    assert RunResult.from_json(r.to_json()) == r
    assert "debug" not in RunResult("r", "passed").to_dict()
    with pytest.raises(ResultError):
        RunResult("r", "passed", debug=["warp_drive"]).to_json()


def test_a_debug_run_never_exits_as_a_pass():
    r = RunResult("r", "passed", debug=["direct_localization"])
    assert run.outcome(r) == run.EXIT_DEBUG == 4
    assert run.outcome(r, expect="passed") == run.EXIT_DEBUG
    assert run.outcome(RunResult("r", "passed")) == run.EXIT_OK


def test_a_debug_runs_line_keeps_the_verdict_first_and_the_mark_last(tmp_path):
    r = RunResult("r1", "passed", debug=["direct_localization"])
    line = run.line(r, tmp_path)
    assert line.split()[:2] == ["passed", "r1"]
    assert line.endswith("[debug: direct_localization; not an evaluation]")


def test_the_debug_options_of_a_stacks_pilots():
    pilots = [{"spec": {"kind": "autoware", "direct_localization": True}},
              {"spec": {"kind": "simple"}}]
    assert run.debug_options(pilots) == ["direct_localization"]
    assert run.debug_options([{"spec": {"kind": "autoware"}}]) == []


def test_runs_shows_the_mark(tmp_path):
    import io
    from scensim import runs
    r = RunResult("r1", "passed", debug=["direct_localization"]).to_dict()
    assert runs.verdict_text(r) == "passed (debug)"
    assert runs.verdict_text(RunResult("r2", "failed").to_dict()) == "failed"
    out = io.StringIO()
    runs._header(tmp_path, r, out)
    assert "debug     direct_localization; not an evaluation" in out.getvalue()
