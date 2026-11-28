"""092 E1b row 3: an exported policy against rsl_rl's own actor, on real checkpoints (CPU).

test_policy_export.py holds the exporter to a numpy reference on a stand-in checkpoint. This
script holds it to rsl_rl itself, on a real checkpoint:
1. it builds rsl_rl 5.5's MLPModel as the training did (the hidden dims and activation given;
   obs_normalization; a Gaussian head);
2. it loads the checkpoint's actor_state_dict into that model;
3. it compares the model's deterministic output (its as_jit form, rsl_rl's own exporter) with
   scensim_batch.policy_export's TorchScript, and with its ONNX where onnxruntime imports.

The observations are either a file of logged ones (`--obs`, an .npy of shape [N, obs_dim]) or,
without one, N draws from the checkpoint's own normalizer statistics (mean + 1.5 std normal).
Run it with Isaac Lab's Python, which has rsl_rl:

    python check_policy_export.py <model_N.pt> [...] [--obs obs.npy] [--n 1000] [--tol 1e-5]

It prints one JSON line per checkpoint: the largest absolute difference of each form, raw and
after the env's clamp (`--env-clip`, what reaches the car). The pass is the raw one's: every
form within `--tol` of rsl_rl's output. It exits 1 if any checkpoint fails.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scensim_batch import policy_export as PE  # noqa: E402


def rsl_rl_actor(sd, hidden, activation):
    from rsl_rl.models.mlp_model import MLPModel
    from tensordict import TensorDict
    n_obs = sd["obs_normalizer._mean"].numel()
    n_act = sd["distribution.std_param"].numel()
    obs = TensorDict({"policy": torch.zeros(1, n_obs)}, batch_size=[1])
    m = MLPModel(obs, {"actor": ["policy"]}, "actor", n_act, hidden_dims=hidden,
                 activation=activation, obs_normalization=True,
                 distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0})
    m.load_state_dict(sd, strict=True)
    return m.eval().as_jit().eval()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoints", nargs="+")
    ap.add_argument("--obs", default="")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--hidden", default="256,128,64")
    ap.add_argument("--activation", default="elu")
    ap.add_argument("--tol", type=float, default=1e-5)
    ap.add_argument("--env-clip", type=float, default=1.0,
                    help="the env's own clamp on the action (094 P4's leadbrake_env: 1.0), "
                         "reported beside the raw comparison; the pass is the raw one's")
    a = ap.parse_args()
    hidden = [int(x) for x in a.hidden.split(",")]
    try:
        import onnxruntime
    except ImportError:
        onnxruntime = None
    bad = 0
    for ck in a.checkpoints:
        sd = torch.load(ck, map_location="cpu", weights_only=False)["actor_state_dict"]
        if a.obs:
            x = np.load(a.obs).astype(np.float32)
            source = f"logged ({Path(a.obs).name})"
        else:
            rng = np.random.default_rng(1)
            m, s = sd["obs_normalizer._mean"].numpy(), sd["obs_normalizer._std"].numpy()
            x = (m + s * rng.standard_normal((a.n, m.shape[-1])) * 1.5).astype(np.float32)
            source = "drawn from the checkpoint's normalizer statistics"
        ref_mod = rsl_rl_actor(sd, hidden, a.activation)
        with torch.no_grad():
            ref = ref_mod(torch.from_numpy(x)).double().numpy()
        d = Path(tempfile.mkdtemp())
        res = {"checkpoint": ck, "n": len(x), "observations": source}
        PE.export(ck, d / "policy.pt", "torchscript", a.activation)
        with torch.no_grad():
            y = torch.jit.load(str(d / "policy.pt"))(torch.from_numpy(x)).double().numpy()
        c = lambda v: np.clip(v, -a.env_clip, a.env_clip)
        res["torchscript_max_abs"] = float(np.abs(y - ref).max())
        res["torchscript_clipped_max_abs"] = float(np.abs(c(y) - c(ref)).max())
        if onnxruntime is not None:
            PE.export(ck, d / "policy.onnx", "onnx", a.activation)
            s = onnxruntime.InferenceSession(str(d / "policy.onnx"),
                                             providers=["CPUExecutionProvider"])
            (yo,) = s.run(["actions"], {"obs": x})
            res["onnx_max_abs"] = float(np.abs(yo.astype(np.float64) - ref).max())
            res["onnx_clipped_max_abs"] = float(np.abs(c(yo.astype(np.float64)) - c(ref)).max())
        res["share_outside_clip"] = round(float((np.abs(ref) > a.env_clip).mean()), 3)
        res["action_range"] = [round(float(ref.min()), 3), round(float(ref.max()), 3)]
        worst = max(v for k, v in res.items() if k.endswith("_max_abs") and "clipped" not in k)
        res["pass"] = worst <= a.tol
        bad += not res["pass"]
        print(json.dumps(res))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
