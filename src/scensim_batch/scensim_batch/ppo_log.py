"""094 P4: rsl_rl PPO's per-update diagnostics, written beside a training run without changing it.

rsl_rl 5.5 logs the losses and the learning rate once per iteration; its adaptive schedule reads
an approx KL per minibatch and throws it away, and it computes no clip fraction at all. This
writes, for every optimizer step of PPO.update (num_learning_epochs x num_mini_batches per
iteration), one JSON line:

    {"update": n, "minibatch": k, "kl_mean": ..., "clip_frac": ..., "lr_used": ..., "lr_after": ...}

- update: the n-th call of PPO.update in this process (the learning iteration of a run from 0);
- kl_mean: actor.get_kl_divergence(the batch's old distribution, the one the minibatch's forward
  made), averaged: the quantity rsl_rl's adaptive schedule compares with desired_kl, computed
  here under every schedule (a fixed one computes none);
- clip_frac: the share of the minibatch whose ratio exp(logp - old_logp) is more than clip_param
  from 1;
- lr_used: the optimizer's learning rate for this step; lr_after: alg.learning_rate after it.

Nothing the update computes is changed: the hooks remember the current batch (the storage's
minibatch generators) and the log-prob the update asked for (actor.get_output_log_prob), and the
values are computed from those under no_grad, before the optimizer steps; no extra forward pass,
no random draw. install(path) puts the hooks on every PPO built after rsl_rl.algorithms.ppo is
imported (train_leadbrake.py does so when PPO_LOG names the file), so this module imports
nothing but the standard library until a PPO exists.
"""
import functools
import importlib.abc
import json
import sys
import threading

MODULE = "rsl_rl.algorithms.ppo"
_installed = set()                 # paths install() was called with (one patch per process)


def attach(alg, path: str) -> None:
    """Put the hooks on one PPO instance; rows are appended to `path`."""
    import torch

    out = open(path, "a", buffering=1)
    state = {"update": -1, "minibatch": 0, "logp": None}
    storage, actor, opt = alg.storage, alg.actor, alg.optimizer

    for name in ("mini_batch_generator", "recurrent_mini_batch_generator"):
        gen = getattr(storage, name, None)
        if gen is None:
            continue

        def remembering(*a, _gen=gen, **k):
            for batch in _gen(*a, **k):
                storage._ppo_log_batch = batch
                yield batch
        setattr(storage, name, functools.wraps(gen)(remembering))

    log_prob = actor.get_output_log_prob

    @functools.wraps(log_prob)
    def remembered(outputs):
        logp = log_prob(outputs)
        state["logp"] = logp
        return logp
    actor.get_output_log_prob = remembered

    step = opt.step

    @functools.wraps(step)
    def logged(*a, **k):
        batch = getattr(storage, "_ppo_log_batch", None)
        row = {"update": state["update"], "minibatch": state["minibatch"]}
        with torch.no_grad():
            old = batch.old_actions_log_prob
            n = old.shape[0]
            new = tuple(p.detach()[:n] for p in actor.output_distribution_params)
            row["kl_mean"] = float(actor.get_kl_divergence(batch.old_distribution_params, new).mean())
            ratio = torch.exp(state["logp"].detach()[:n] - torch.squeeze(old))
            row["clip_frac"] = float(((ratio - 1.0).abs() > alg.clip_param).float().mean())
        row["lr_used"] = float(opt.param_groups[0]["lr"])
        result = step(*a, **k)
        row["lr_after"] = float(alg.learning_rate)
        out.write(json.dumps(row) + "\n")
        state["minibatch"] += 1
        return result
    opt.step = logged

    update = alg.update

    @functools.wraps(update)
    def counted(*a, **k):
        state["update"] += 1
        state["minibatch"] = 0
        return update(*a, **k)
    alg.update = counted


def _patch(mod, path: str) -> None:
    cls = getattr(mod, "PPO", None)
    if not isinstance(cls, type) or getattr(cls, "_ppo_log", False):
        return
    init = cls.__init__

    @functools.wraps(init)
    def built(self, *a, **k):
        init(self, *a, **k)
        attach(self, path)
    cls.__init__ = built
    cls._ppo_log = True


class _Loader(importlib.abc.Loader):
    def __init__(self, inner, path):
        self.inner, self.path = inner, path

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        self.inner.exec_module(module)
        _patch(module, self.path)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class _Finder(importlib.abc.MetaPathFinder):
    """Finds rsl_rl.algorithms.ppo through the other finders (another hook's included: a
    thread-local guard stops the two asking each other forever) and wraps its loader."""

    def __init__(self, path):
        self.path, self.busy = path, threading.local()

    def find_spec(self, name, path, target=None):
        if name != MODULE or getattr(self.busy, "on", False):
            return None
        self.busy.on = True
        try:
            for finder in sys.meta_path:
                if finder is self or not hasattr(finder, "find_spec"):
                    continue
                spec = finder.find_spec(name, path, target)
                if spec is not None:
                    if spec.loader is not None and hasattr(spec.loader, "exec_module"):
                        spec.loader = _Loader(spec.loader, self.path)
                    return spec
            return None
        finally:
            self.busy.on = False


def install(path: str) -> None:
    """Attach the hooks to every PPO built from now on: rsl_rl.algorithms.ppo's PPO, imported
    already or later. Once per process."""
    if _installed:
        return
    _installed.add(path)
    mod = sys.modules.get(MODULE)
    if mod is not None:
        _patch(mod, path)
    else:
        sys.meta_path.insert(0, _Finder(path))
