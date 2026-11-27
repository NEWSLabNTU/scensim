"""Issue 195 A9: the GNSS receiver's error is a project setting, the pilot's `gnss_noise_*`
arguments, which scensim routes to the simulator's vehicle side (acb's parameters on CARLA,
aib's ego config `gnss` block on Isaac) with an explicit seed, so a scensim run reproduces."""

import pytest

from scensim import stack

import test_stack
from test_stack import make


@pytest.fixture
def where(host):
    """test_stack's seat and logs under tmp."""
    return test_stack.where.__wrapped__(host)


@pytest.fixture
def aib_ego(tmp_path, monkeypatch):
    base = tmp_path / "aib" / "ego.yaml"
    base.parent.mkdir()
    base.write_text("rig: tesla_model3.rig.yaml\ndomain: 1\n")
    monkeypatch.setattr(stack, "aib_ego_config", lambda: base)
    return base


def _with_args(d, args: str):
    tb = d / "testbench.yaml"
    text = tb.read_text()
    assert "kind: autoware" in text
    tb.write_text(text.replace("kind: autoware", f"kind: autoware, args: {{{args}}}", 1))


def test_an_isaac_ego_gets_an_explicit_seed(where, maps_hub, aib_ego):
    d = make(where, template="isaac")
    p = stack.plan(project_arg=str(d))
    assert p.record["isaac_ego"]["config"]["gnss"] == {"seed": 0}
    assert f"ego:={p.stack_dir / stack.ISAAC_EGO}" in p.launch_args["sim_args"]


def test_the_pilots_gnss_args_reach_the_isaac_ego_config(where, maps_hub, aib_ego):
    d = make(where, template="isaac")
    _with_args(d, "gnss_noise_horizontal_stddev_m: 0.05, gnss_noise_enabled: true, "
                  "gnss_noise_seed: 7")
    gnss = stack.plan(project_arg=str(d)).record["isaac_ego"]["config"]["gnss"]
    assert gnss == {"horizontal_stddev_m": 0.05, "enabled": True, "seed": 7}


def test_a_fresh_seed_is_asked_for_by_minus_one(where, maps_hub, aib_ego):
    d = make(where, template="isaac")
    _with_args(d, "gnss_noise_seed: -1")
    assert stack.plan(project_arg=str(d)).record["isaac_ego"]["config"]["gnss"] == {"seed": None}


def test_gnss_args_layer_onto_a_users_ego_config(where, maps_hub, aib_ego, tmp_path):
    d = make(where, template="isaac")
    _with_args(d, "gnss_noise_horizontal_stddev_m: 0.05")
    (d / "config").mkdir(exist_ok=True)
    (d / "config" / "my_ego.yaml").write_text("rig: x.rig.yaml\ngnss: {vertical_stddev_m: 0.1}\n")
    tb = d / "testbench.yaml"
    tb.write_text(tb.read_text() + "isaac: {ego: config/my_ego.yaml}\n")
    cfg = stack.plan(project_arg=str(d)).record["isaac_ego"]["config"]
    assert cfg["rig"].endswith("x.rig.yaml")
    assert cfg["gnss"] == {"vertical_stddev_m": 0.1, "horizontal_stddev_m": 0.05, "seed": 0}


def test_a_carla_ego_gets_an_explicit_seed(where, maps_hub):
    d = make(where)
    p = stack.plan(project_arg=str(d))
    sided = [e for e in p.record["pilot_entries"] if e["kind"] == "autoware"]
    assert sided and all(e["args"]["gnss_noise_seed"] == 0 for e in sided)


def test_a_carla_egos_own_seed_is_kept(where, maps_hub):
    d = make(where)
    _with_args(d, "gnss_noise_seed: 7")
    p = stack.plan(project_arg=str(d))
    [e] = [e for e in p.record["pilot_entries"] if e["kind"] == "autoware"][:1]
    assert e["args"]["gnss_noise_seed"] == 7
