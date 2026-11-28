"""092 E1b: an rsl_rl actor checkpoint exported as a pilot's model.

A policy trained through K2 (094 P4's lead-brake task, for one) is evaluated on seats as an
ordinary pilot (ml-training-interface.md section 6). That pilot loads a model file, not rsl_rl.
This module rebuilds the actor from the checkpoint's tensors and writes it as TorchScript or
ONNX, with a record beside it (`<model>.json`, schema `scensim.policy_export/1`):
- the checkpoint's sha256 and iteration;
- the shapes;
- the activation and the normalizer's epsilon;
- the model file's sha256.

The actor is rsl_rl 5.5's MLPModel, deterministic:
- `EmpiricalNormalization`: (x - mean) / (std + 1e-2);
- the MLP: Linear layers with the activation between them;
- a Gaussian head with a state-independent std, whose deterministic output is the MLP's own
  output (the mean).

That is the layout of 094 P4's `model_N.pt` (rsl-rl-lib 5.5.1). This module imports no rsl_rl,
so it runs in any interpreter with torch, the gate's included.

A checkpoint it would misread is refused by name (`ExportError`) and never exported:
- a missing normalizer tensor;
- a gap in the layers;
- a heteroscedastic or Beta head (a std per output row);
- a recurrent or unknown key;
- an activation it does not know.

The training env's `clip_actions` is applied by the env wrapper, not by the actor, so a pilot
applies it after the model. `export` records it when given.

    python3 -m scensim_batch.policy_export <model_N.pt> -o policy.pt [--format torchscript|onnx]
        [--activation elu] [--clip-actions 1.0]
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import torch
from torch import nn

SCHEMA = "scensim.policy_export/1"
EPS = 1e-2                       # rsl_rl 5.5's EmpiricalNormalization default
NORM = ("obs_normalizer._mean", "obs_normalizer._var", "obs_normalizer._std",
        "obs_normalizer.count")
HEADS = ("distribution.std_param", "distribution.log_std_param")     # scalar and log std types
ACTIVATIONS = {"elu": nn.ELU, "relu": nn.ReLU, "tanh": nn.Tanh, "selu": nn.SELU,
               "lrelu": nn.LeakyReLU, "sigmoid": nn.Sigmoid}
LAYER = re.compile(r"mlp\.(\d+)\.(weight|bias)$")


class ExportError(ValueError):
    pass


class Actor(nn.Module):
    """The deterministic actor: normalizer, then the MLP. Input [N, obs_dim], output [N, act]."""

    def __init__(self, mean, std, layers, activation):
        super().__init__()
        self.register_buffer("mean", mean.reshape(1, -1).float())
        self.register_buffer("std", std.reshape(1, -1).float())
        self.eps = EPS
        mods = []
        for k, lin in enumerate(layers):
            mods.append(lin)
            if k < len(layers) - 1:
                mods.append(ACTIVATIONS[activation]())
        self.mlp = nn.Sequential(*mods)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.mlp((obs - self.mean) / (self.std + self.eps))


def _load(checkpoint):
    try:
        doc = torch.load(str(checkpoint), map_location="cpu", weights_only=False)
    except TypeError:            # torch before 1.13 has no weights_only
        doc = torch.load(str(checkpoint), map_location="cpu")
    if not isinstance(doc, dict) or "actor_state_dict" not in doc:
        raise ExportError(f"{checkpoint}: not an rsl_rl checkpoint (no actor_state_dict)")
    return doc


def _layers(sd, checkpoint):
    """The MLP's Linear layers from mlp.{0,2,4,...}, refusing a gap or a mismatched shape."""
    idx = {}
    for k in sd:
        m = LAYER.match(k)
        if m:
            idx.setdefault(int(m.group(1)), set()).add(m.group(2))
    if not idx:
        raise ExportError(f"{checkpoint}: no mlp.N.weight in actor_state_dict")
    want = list(range(0, 2 * len(idx), 2))
    for i in want:
        for part in ("weight", "bias"):
            if part not in idx.get(i, ()):
                raise ExportError(f"{checkpoint}: mlp.{i}.{part} missing: the layers are "
                                  f"mlp.{{0,2,4,...}} with no gap")
    if sorted(idx) != want:
        extra = sorted(set(idx) - set(want))[0]
        raise ExportError(f"{checkpoint}: mlp.{extra}.weight is not at an even index after "
                          f"mlp.0 to mlp.{want[-1]}")
    layers = []
    for i in want:
        w, b = sd[f"mlp.{i}.weight"], sd[f"mlp.{i}.bias"]
        if layers and w.shape[1] != layers[-1].out_features:
            raise ExportError(f"{checkpoint}: mlp.{i}.weight takes {w.shape[1]} inputs, the layer "
                              f"before gives {layers[-1].out_features}")
        lin = nn.Linear(w.shape[1], w.shape[0])
        with torch.no_grad():
            lin.weight.copy_(w.float())
            lin.bias.copy_(b.float())
        layers.append(lin)
    return layers


def load_actor(checkpoint, activation="elu"):
    """The checkpoint's deterministic actor as a plain torch module (eval mode, CPU)."""
    if activation not in ACTIVATIONS:
        raise ExportError(f"activation {activation!r}: one of {', '.join(sorted(ACTIVATIONS))}")
    sd = _load(checkpoint)["actor_state_dict"]
    for k in NORM[0], NORM[2]:
        if k not in sd:
            raise ExportError(f"{checkpoint}: {k} missing: an actor trained with "
                              f"obs_normalization=True is expected")
    heads = [k for k in sd if k.startswith("distribution.")]
    for k in heads:
        if k not in HEADS:
            raise ExportError(f"{checkpoint}: {k}: only a Gaussian head with a state-independent "
                              f"std ({' or '.join(HEADS)}) is exported")
    known = set(NORM) | set(HEADS)
    for k in sd:
        if k not in known and not LAYER.match(k):
            raise ExportError(f"{checkpoint}: {k}: not part of an rsl_rl 5.5 MLP actor")
    layers = _layers(sd, checkpoint)
    n_obs, n_act = layers[0].in_features, layers[-1].out_features
    for k in heads:
        if tuple(sd[k].shape) != (n_act,):
            raise ExportError(f"{checkpoint}: {k} has shape {tuple(sd[k].shape)}, not ({n_act},): "
                              f"a std per output row is a heteroscedastic or Beta head")
    if sd[NORM[0]].numel() != n_obs or sd[NORM[2]].numel() != n_obs:
        raise ExportError(f"{checkpoint}: the normalizer has {sd[NORM[0]].numel()} observations, "
                          f"mlp.0 takes {n_obs}")
    return Actor(sd[NORM[0]], sd[NORM[2]], layers, activation).eval()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(checkpoint, out, fmt="torchscript", activation="elu", clip_actions=None):
    """Write the actor to `out` (TorchScript or ONNX) and its record to `out`.json; return it."""
    actor = load_actor(checkpoint, activation)
    doc = _load(checkpoint)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_obs = actor.mlp[0].in_features
    if fmt == "torchscript":
        torch.jit.script(actor).save(str(out))
    elif fmt == "onnx":
        kw = {"input_names": ["obs"], "output_names": ["actions"],
              "dynamic_axes": {"obs": {0: "batch"}, "actions": {0: "batch"}}, "opset_version": 13}
        try:
            torch.onnx.export(actor, (torch.zeros(1, n_obs),), str(out), dynamo=False, **kw)
        except TypeError:        # torch before 2.5 has no dynamo argument
            torch.onnx.export(actor, (torch.zeros(1, n_obs),), str(out), **kw)
    else:
        raise ExportError(f"format {fmt!r}: torchscript or onnx")
    lins = [m for m in actor.mlp if isinstance(m, nn.Linear)]
    meta = {
        "schema": SCHEMA, "format": fmt, "layout": "rsl_rl 5.5 MLPModel, deterministic",
        "checkpoint": {"file": Path(checkpoint).name, "sha256": _sha(checkpoint),
                       "iter": doc.get("iter")},
        "obs_dim": n_obs, "action_dim": lins[-1].out_features,
        "hidden_dims": [m.out_features for m in lins[:-1]],
        "activation": activation, "normalizer_eps": EPS, "clip_actions": clip_actions,
        "input": "obs", "output": "actions",
        "model": {"file": out.name, "sha256": _sha(out)},
    }
    Path(f"{out}.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("checkpoint")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--format", choices=("torchscript", "onnx"), default="torchscript")
    ap.add_argument("--activation", default="elu")
    ap.add_argument("--clip-actions", type=float, default=None)
    a = ap.parse_args(argv)
    try:
        meta = export(a.checkpoint, a.out, a.format, a.activation, a.clip_actions)
    except ExportError as e:
        print(f"policy_export: {e}", file=sys.stderr)
        return 2
    print(f"policy_export: {a.out} ({meta['format']}, {meta['obs_dim']} -> "
          f"{meta['action_dim']}), checkpoint {meta['checkpoint']['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
