"""scensim issue 100: the brake module's slip offset became the spec's own key,
brakes.estimator.slip_offset, instead of following isaac.physx.min_active_slip_denominator. The
RoboRacer writes 0.5, the value its estimate took from its denominator before, and its ABS and
TC are as they were (sim_vehicle_ecu 3b3355a)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parents[2] / "src"
sys.path[:0] = [str(SRC / "sim_vehicle_spec"), str(SRC / "sim_vehicle_ecu")]

from sim_vehicle_ecu.calibration import Calibration  # noqa: E402
from sim_vehicle_spec import spec as specmod  # noqa: E402


def test_its_onboard_computer_is_as_before():
    sp = specmod.load(ROOT / "vehicles/roboracer.yaml")
    c = Calibration.from_spec(sp.doc)
    assert c.est_slip_offset == 0.5
    assert sp.doc["isaac"]["physx"]["min_active_slip_denominator"] == c.est_slip_offset
    assert (c.abs_enabled, c.abs_slip_release, c.abs_slip_reapply) == (False, 0.25, 0.15)
    assert (c.tc_slip_limit, c.tc_slip_reapply) == (0.25, 0.15)
