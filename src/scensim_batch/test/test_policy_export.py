"""092 E1b row 3: scensim_batch.policy_export, an rsl_rl actor checkpoint exported as a pilot's
model (TorchScript; ONNX where onnx and onnxruntime import), checked against the checkpoint.

The reference is computed here in numpy from the checkpoint's tensors as rsl_rl 5.5's MLPModel
runs them (EmpiricalNormalization (x - mean) / (std + 1e-2), Linear and ELU layers, a Gaussian
head whose deterministic output is the MLP's), not by the module under test. The checkpoint is a
stand-in in rsl_rl 5.5.1's actor_state_dict layout, at 094 P4's shape (9 observations, 256-128-64,
2 actions); 1000 observations are drawn from its normalizer's statistics. An exported model must
give the reference's actions within 1e-5 on all of them. Skipped without torch."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

try:
    import torch
except ImportError:            # the gate's interpreter may have none
    torch = None
try:
    import onnxruntime
except ImportError:            # not in the gate's interpreter
    onnxruntime = None
if importlib.util.find_spec("onnx") is None:      # torch.onnx.export needs it
    onnxruntime = None

TOL = 1e-5
OBS, HIDDEN, ACT = 9, (256, 128, 64), 2


def stand_in_checkpoint(path, seed=0, hidden=HIDDEN, extra=None, drop=None):
    """An rsl_rl 5.5.1 checkpoint: actor_state_dict's keys and shapes as 094 P4's model_N.pt."""
    g = torch.Generator().manual_seed(seed)
    sd = {"obs_normalizer._mean": torch.randn(1, OBS, generator=g) * 3.0,
          "obs_normalizer._var": torch.rand(1, OBS, generator=g) * 4.0 + 0.01}
    sd["obs_normalizer._std"] = sd["obs_normalizer._var"].sqrt()
    sd["obs_normalizer.count"] = torch.tensor(123456)
    sd["distribution.std_param"] = torch.full((ACT,), 0.3)
    dims = [OBS, *hidden, ACT]
    for k in range(len(dims) - 1):
        sd[f"mlp.{2 * k}.weight"] = torch.randn(dims[k + 1], dims[k], generator=g) / dims[k] ** 0.5
        sd[f"mlp.{2 * k}.bias"] = torch.randn(dims[k + 1], generator=g) * 0.1
    sd.update(extra or {})
    for k in drop or ():
        del sd[k]
    torch.save({"actor_state_dict": sd, "critic_state_dict": {}, "optimizer_state_dict": {},
                "iter": 1499, "infos": None}, path)
    return sd


def reference(sd, x):
    """rsl_rl 5.5's MLPModel, deterministic, in float64 numpy from the checkpoint's tensors."""
    a = lambda k: sd[k].double().numpy()
    h = (x - a("obs_normalizer._mean")) / (a("obs_normalizer._std") + 1e-2)
    n = sum(1 for k in sd if k.startswith("mlp.") and k.endswith(".weight"))
    for k in range(n):
        h = h @ a(f"mlp.{2 * k}.weight").T + a(f"mlp.{2 * k}.bias")
        if k < n - 1:
            h = np.where(h > 0, h, np.expm1(np.minimum(h, 0)))      # ELU, alpha 1
    return h


def observations(sd, n=1000, seed=1):
    rng = np.random.default_rng(seed)
    m, s = sd["obs_normalizer._mean"].numpy(), sd["obs_normalizer._std"].numpy()
    return (m + s * rng.standard_normal((n, OBS)) * 1.5).astype(np.float32)


@unittest.skipIf(torch is None, "no torch")
class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scensim_batch import policy_export as PE
        cls.PE = PE
        cls.d = Path(tempfile.mkdtemp())
        cls.ckpt = cls.d / "model_1499.pt"
        cls.sd = stand_in_checkpoint(cls.ckpt)
        cls.x = observations(cls.sd)
        cls.ref = reference(cls.sd, cls.x.astype(np.float64))

    def test_the_rebuilt_actor_is_the_checkpoint_s(self):
        actor = self.PE.load_actor(self.ckpt)
        with torch.no_grad():
            y = actor(torch.from_numpy(self.x)).numpy()
        self.assertEqual(y.shape, (1000, ACT))
        self.assertLess(float(np.abs(y - self.ref).max()), TOL)

    def test_torchscript_gives_the_checkpoint_s_actions(self):
        meta = self.PE.export(self.ckpt, self.d / "ts" / "policy.pt", fmt="torchscript")
        m = torch.jit.load(str(self.d / "ts" / "policy.pt"))
        with torch.no_grad():
            y = m(torch.from_numpy(self.x)).numpy()
        self.assertLess(float(np.abs(y - self.ref).max()), TOL)
        self.assertEqual(meta["format"], "torchscript")

    @unittest.skipIf(onnxruntime is None, "no onnx or onnxruntime")
    def test_onnx_gives_the_checkpoint_s_actions(self):
        self.PE.export(self.ckpt, self.d / "ox" / "policy.onnx", fmt="onnx")
        s = onnxruntime.InferenceSession(str(self.d / "ox" / "policy.onnx"),
                                         providers=["CPUExecutionProvider"])
        (y,) = s.run(["actions"], {"obs": self.x})
        self.assertLess(float(np.abs(y - self.ref).max()), TOL)

    def test_the_model_s_record_names_its_checkpoint(self):
        meta = self.PE.export(self.ckpt, self.d / "rec" / "policy.pt", fmt="torchscript")
        on_disk = json.loads((self.d / "rec" / "policy.pt.json").read_text())
        self.assertEqual(meta, on_disk)
        self.assertEqual(meta["schema"], "scensim.policy_export/1")
        self.assertEqual(meta["checkpoint"]["sha256"],
                         hashlib.sha256(self.ckpt.read_bytes()).hexdigest())
        self.assertEqual(meta["checkpoint"]["iter"], 1499)
        self.assertEqual((meta["obs_dim"], meta["action_dim"]), (OBS, ACT))
        self.assertEqual(meta["hidden_dims"], list(HIDDEN))
        self.assertEqual(meta["activation"], "elu")
        self.assertEqual(meta["normalizer_eps"], 1e-2)
        self.assertEqual(meta["model"]["sha256"],
                         hashlib.sha256((self.d / "rec" / "policy.pt").read_bytes()).hexdigest())

    def test_the_same_checkpoint_exports_the_same_actions(self):
        a = self.PE.load_actor(self.ckpt)
        b = self.PE.load_actor(self.ckpt)
        with torch.no_grad():
            xa, xb = a(torch.from_numpy(self.x)), b(torch.from_numpy(self.x))
        self.assertTrue(torch.equal(xa, xb))


@unittest.skipIf(torch is None, "no torch")
class Refusals(unittest.TestCase):
    """A checkpoint this exporter would misread is refused by name, never exported."""

    def refused(self, **kw):
        from scensim_batch import policy_export as PE
        d = Path(tempfile.mkdtemp())
        stand_in_checkpoint(d / "m.pt", **kw)
        with self.assertRaises(PE.ExportError) as e:
            PE.load_actor(d / "m.pt")
        return str(e.exception)

    def test_a_checkpoint_without_its_normalizer_is_refused(self):
        self.assertIn("obs_normalizer._std", self.refused(drop=["obs_normalizer._std"]))

    def test_a_heteroscedastic_or_beta_head_is_refused(self):
        msg = self.refused(extra={"distribution.std_param": torch.zeros(2, ACT)})
        self.assertIn("distribution.std_param", msg)

    def test_an_unknown_key_is_refused(self):
        self.assertIn("rnn.weight_ih_l0", self.refused(extra={"rnn.weight_ih_l0": torch.zeros(1)}))

    def test_a_gap_in_the_layers_is_refused(self):
        self.assertIn("mlp.4.weight", self.refused(drop=["mlp.4.weight", "mlp.4.bias"]))

    def test_an_unknown_activation_is_refused(self):
        from scensim_batch import policy_export as PE
        d = Path(tempfile.mkdtemp())
        stand_in_checkpoint(d / "m.pt")
        with self.assertRaises(PE.ExportError) as e:
            PE.load_actor(d / "m.pt", activation="swish")
        self.assertIn("swish", str(e.exception))


if __name__ == "__main__":
    unittest.main()
