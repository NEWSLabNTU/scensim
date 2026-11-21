"""The batched VESC on torch (scensim 092 K2.2c): one code over sim_vehicle_ecu.xp, so a torch
batch, on the CPU and on a GPU, equals the numpy batch (the reference) bit for bit over the
same random sequences as test_batch.py's: every mode, the latency queue and its jitter per
seed, stale commands, missing readings and resets. The torch batch takes and gives tensors on
its device; nothing in its per-step path comes back to the host without jitter."""
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from roboracer_vesc.component import RoboRacerVesc  # noqa: E402
from sim_vehicle_ecu import batch as B  # noqa: E402
from test_batch import CAR, DT, sequence  # noqa: E402

DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


def to_dev(d, device):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = to_dev(v, device)
        else:
            out[k] = torch.as_tensor(np.asarray(v), device=device)
    return out


def bits(a):
    a = a.detach().cpu().numpy() if torch.is_tensor(a) else np.asarray(a)
    return a.astype(a.dtype).tobytes()


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("n,jitter", [(8, 0.0), (32, 0.004)])
def test_torch_equals_numpy_bit_for_bit(device, n, jitter):
    params = {"latency_jitter": jitter} if jitter else {}
    seeds = [11 + i for i in range(n)]
    ref = B.load_batch(RoboRacerVesc, CAR, params, seeds)
    tb = B.load_batch(RoboRacerVesc, CAR, params, seeds, array_api="torch", device=device)
    assert tb.array_api_in_use == "torch" and tb.xp.device.type == device
    for cmds, sens, resets in sequence(n, 1500, seed=n):
        if resets.any():
            ref.reset_batch(resets)
            tb.reset_batch(torch.as_tensor(resets, device=device))
        c, s = B.commands_to_batch("vesc", cmds), B.sensors_to_batch(sens)
        a = B.checked_batch(ref.step_batch(c, s, DT), n)
        b = B.checked_batch(tb.step_batch(to_dev(c, device), to_dev(s, device), DT), n)
        assert b["drive"].device.type == device
        for f in ("drive", "brake", "tire_angle"):
            assert bits(a[f]) == bits(b[f]), f
        for k in a["telemetry"]:
            assert bits(a["telemetry"][k]) == bits(b["telemetry"][k]), k


def test_a_namespace_it_lacks_is_refused():
    with pytest.raises(B.BatchError, match="no batched form on array_api 'warp'"):
        B.load_batch(RoboRacerVesc, CAR, {}, [1], array_api="warp")
