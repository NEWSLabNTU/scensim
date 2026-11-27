"""An arg only the scensim profile takes, given to a stock autoware pilot, is refused by name
instead of being ignored (issue 180; no shims, refuse by name). The list is the pilot launch's own:
what pilots/autoware.launch.xml passes to the scensim profile's include and not to the stock one."""

import os
import xml.etree.ElementTree as ET

import pytest

from scensim import project

from test_project import make, scenario_checks, whats

PILOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scensim_launch",
                     "launch", "pilots", "autoware.launch.xml")


def tb(pilot: str) -> str:
    return f"simulator: carla\nassets: []\npilots:\n  ego: {pilot}\n"


def included_args():
    """{profile: [arg names its include passes]} from the pilot launch's two groups."""
    out = {}
    for g in ET.parse(PILOT).getroot().iter("group"):
        for prof in ("stock", "scensim"):
            if f"'{prof}'" in (g.get("if") or ""):
                out[prof] = [a.get("name") for i in g.findall("include") for a in i.findall("arg")]
    return out


def test_the_list_is_the_pilot_launchs_scensim_only_args():
    inc = included_args()
    only = set(inc["scensim"]) - set(inc["stock"]) - {"autoware_launch"}
    assert set(project.SCENSIM_PROFILE_ARGS) == only


@pytest.mark.parametrize("profile", ["", ", autoware_profile: stock"])
@pytest.mark.parametrize("arg,value", [("compare_map_z_ratio", 0.2), ("lane_height_check", "true"),
                                       ("max_velocity", 8), ("gnss_particle_yaw_variance", 1e-4)])
def test_a_scensim_profile_arg_on_a_stock_pilot_is_refused_by_name(host, profile, arg, value):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3" + profile
                             + f", args: {{{arg}: {value}}}}}"))
    [f] = [f for f in scenario_checks(d) if arg in f.what]
    assert "stock" in f.what and "autoware_profile: scensim" in f.fix


def test_the_same_args_on_a_scensim_pilot_pass(host):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, autoware_profile: scensim, "
                             "args: {compare_map_z_ratio: 0.2, lane_height_check: 'true'}}"))
    assert not [w for w in whats(scenario_checks(d))
                if "compare_map_z_ratio" in w or "lane_height_check" in w]


def test_a_stock_pilot_with_its_own_autoware_args_passes(host):
    d = make(host["tmp"], tb("{kind: autoware, vehicle: tesla_model3, "
                             "args: {lidar_detection_model: centerpoint}}"))
    assert not [w for w in whats(scenario_checks(d)) if "lidar_detection_model" in w]
