"""K2.2c: BatchRun resident on a GPU equals the CPU path. The same compiled scenario
(cs2: an SSv2 default lead and a storyboard that brakes it), the same commands, once on the
CPU with a numpy component (the reference: the CPU contract) and once compiled, stepped and
observed on cuda with the component on torch there (array_api "torch"): every entity's pose
and speed agree to 1e-9 (bit for bit where no transcendental is computed; CUDA's sin, cos and
atan2 may differ from the CPU's in the last bit), the storyboard's states and the outcomes
exactly. Skipped without torch 2 and a GPU it has kernels for (the Isaac Lab venv's)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

try:
    import numpy as np
    import torch
    from sim_vehicle_ecu import batch as ecu_batch
    from sim_vehicle_ecu import xp as xpmod
    CUDA = (int(torch.__version__.split(".")[0]) >= 2 and torch.cuda.is_available()
            and torch.zeros(1, device="cuda").add(1).item() == 1.0)
except Exception:   # noqa: BLE001 - no torch, or a GPU it cannot run on
    CUDA = False

from test_core import CASES, DT, MASS, RADIUS, PointMass, StraightWorld, cmds  # noqa: E402


class AccelXBatch:
    """test_core's AccelBatch written over sim_vehicle_ecu.xp: numpy and torch."""
    commands, truth = "autoware", ()
    array_api = ("numpy", "torch")

    def __init__(self, vehicle, params, seeds, xp=None):
        self.xp = xp or xpmod.namespace("numpy")
        self.n = len(seeds)

    def reset_batch(self, mask):
        pass

    def step_batch(self, c, s, dt):
        xp = self.xp
        a = xp.where(xp.asarray(c["valid"], xp.bool), xp.asarray(c["acceleration"], xp.float64),
                     0.0)
        torque = a * MASS * RADIUS
        zero = xp.zeros(self.n)
        rear_d = xp.where(torque > 0, torque / 2, zero)
        rear_b = xp.where(torque < 0, -torque / 2, zero)
        drive = xp.zeros((self.n, 4))
        brake = xp.zeros((self.n, 4))
        drive[:, 2], drive[:, 3] = rear_d, rear_d
        brake[:, 2], brake[:, 3] = rear_b, rear_b
        return {"drive": drive, "brake": brake, "tire_angle": xp.zeros(self.n)}


class AccelX:
    batch = AccelXBatch


@unittest.skipUnless(CUDA, "no torch 2 with a usable GPU")
class DeviceResident(unittest.TestCase):
    def run_on(self, device, recs, steps):
        from scensim_batch import compile as C, core
        ctx = torch.device(device) if device != "cpu" else None
        if ctx is not None:
            ctx.__enter__()
        try:
            c = C.compile_scenario(CASES / "cs2_lead_brakes_wet_night.xosc", recs,
                                   StraightWorld(), provides=("world knob illumination=night",),
                                   device=device)
            c.y[:, c.index("ego")] = 3.5      # the next lane, as test_core's
            backend = PointMass(c.n)
        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)
        api = "torch" if device != "cpu" else "numpy"
        comp = ecu_batch.load_batch(AccelX, {}, {}, [7] * len(recs), array_api=api,
                                    device=device if api == "torch" else None)
        run = core.BatchRun(c, StraightWorld(), backend, comp, device=device)
        run.route_length = 1000.0
        run.reset()
        out = []
        for k in range(steps):
            a = 1.0 if k < 40 else -2.0
            cm = cmds(len(recs), a)
            if device != "cpu":
                cm = {f: torch.as_tensor(v, device=device) for f, v in cm.items()}
            obs = run.step(cm, DT)
            states = {p: int(run.storyboard.state[id(node)][0])
                      for p, node in _paths(run.storyboard).items()}
            out.append(({f: obs[f].detach().cpu().clone() for f in ("x", "y", "yaw", "v")},
                        states, [o for o in run.outcome()]))
        return c, run, out

    def test_cuda_equals_the_cpu_path(self):
        recs = [{"values": {"ego_speed": 20.0, "lead_speed": 22.0, "onset_s": 3.0}},
                {"values": {"ego_speed": 10.0, "onset_s": 2.0}}]
        _, cpu_run, cpu = self.run_on("cpu", recs, 120)
        _, gpu_run, gpu = self.run_on("cuda", recs, 120)
        self.assertEqual(gpu_run.obs["x"].device.type, "cuda")
        self.assertEqual(gpu_run.storyboard.outcome.device.type, "cuda")
        for k, ((a, sa, oa), (b, sb, ob)) in enumerate(zip(cpu, gpu)):
            for f in a:
                self.assertTrue(torch.allclose(a[f], b[f], rtol=0, atol=1e-9),
                                (k, f, (a[f] - b[f]).abs().max().item()))
            self.assertEqual(sa, sb, k)
            self.assertEqual(oa, ob, k)


def _paths(sb):
    from scensim_batch import agreement as A
    return A.element_paths(sb)


if __name__ == "__main__":
    unittest.main()
