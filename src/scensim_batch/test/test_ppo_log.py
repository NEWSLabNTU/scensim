"""094 P4: scensim_batch.ppo_log, the per-update PPO diagnostics (approx KL, clip fraction, the
learning rate) written beside a training run, without changing it.

The hooks go on a PPO instance (its storage's minibatch generator, its actor's log-prob, its
optimizer's step and its update), so they are tested here on a small stand-in with rsl_rl's
shape: an actor with a Gaussian head and rsl_rl's model API (output_distribution_params,
get_output_log_prob, get_kl_divergence), a storage yielding rsl_rl's batch fields, and an update
that runs rsl_rl 5.5's PPO loop (forward, log-prob, clipped surrogate, step). The import hook
(install) is tested on a stand-in rsl_rl.algorithms.ppo module. Skipped without torch."""
import importlib
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

try:
    import torch
except ImportError:            # the gate's interpreter may have none
    torch = None

from scensim_batch import ppo_log  # noqa: E402 (stdlib only at import)


def stand_in(seed=0, n=8, schedule="fixed", lr=1e-3, epochs=2, minibatches=2, clip=0.2):
    """A PPO-shaped object (see the module docstring); every random draw is made here."""
    g = torch.Generator().manual_seed(seed)

    class Actor(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lin = torch.nn.Linear(3, 2)
            self.log_std = torch.nn.Parameter(torch.zeros(2))
            with torch.no_grad():
                self.lin.weight.copy_(torch.randn(2, 3, generator=g))
                self.lin.bias.copy_(torch.randn(2, generator=g))
            self.distribution = None

        def forward(self, obs, masks=None, hidden_state=None, stochastic_output=True):
            self.distribution = torch.distributions.Normal(self.lin(obs), self.log_std.exp())
            return self.distribution.mean

        @property
        def output_distribution_params(self):
            return (self.distribution.mean, self.distribution.stddev)

        def get_output_log_prob(self, outputs):
            return self.distribution.log_prob(outputs).sum(-1)

        def get_kl_divergence(self, old, new):
            (m0, s0), (m1, s1) = old, new
            return (torch.log(s1 / s0) + (s0 ** 2 + (m0 - m1) ** 2) / (2 * s1 ** 2) - 0.5).sum(-1)

    actor = Actor()
    obs = torch.randn(n, 3, generator=g)
    with torch.no_grad():
        actor(obs)
        actions = actor.distribution.mean + 0.3 * torch.randn(n, 2, generator=g)
        old_logp = actor.get_output_log_prob(actions)
        old_params = tuple(p.clone() for p in actor.output_distribution_params)
    adv = torch.randn(n, generator=g)

    class Storage:
        def mini_batch_generator(self, num_mini_batches, num_epochs=8):
            size = n // num_mini_batches
            for _ in range(num_epochs):
                for i in range(num_mini_batches):
                    k = slice(i * size, (i + 1) * size)
                    yield types.SimpleNamespace(
                        observations=obs[k], actions=actions[k], advantages=adv[k],
                        old_actions_log_prob=old_logp[k].unsqueeze(-1),
                        old_distribution_params=tuple(p[k] for p in old_params),
                        masks=None, hidden_states=(None, None))

    class PPO:
        def __init__(self):
            self.actor, self.storage = actor, Storage()
            self.optimizer = torch.optim.Adam(actor.parameters(), lr=lr)
            self.learning_rate, self.schedule, self.clip_param = lr, schedule, clip
            self.num_learning_epochs, self.num_mini_batches = epochs, minibatches

        def update(self):
            for batch in self.storage.mini_batch_generator(self.num_mini_batches, self.num_learning_epochs):
                self.actor(batch.observations, masks=batch.masks, hidden_state=batch.hidden_states[0])
                logp = self.actor.get_output_log_prob(batch.actions)
                if self.schedule == "adaptive":        # a stand-in schedule: halve every minibatch
                    self.learning_rate /= 2
                    for pg in self.optimizer.param_groups:
                        pg["lr"] = self.learning_rate
                ratio = torch.exp(logp - torch.squeeze(batch.old_actions_log_prob))
                a = torch.squeeze(batch.advantages)
                loss = torch.max(-a * ratio, -a * torch.clamp(ratio, 1 - self.clip_param,
                                                                 1 + self.clip_param)).mean()
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
            return {"surrogate": float(loss)}

    return PPO(), obs, actions


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


@unittest.skipIf(torch is None, "no torch")
class AttachTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ppo.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_row_per_optimizer_step_numbered_by_update(self):
        alg, _, _ = stand_in(epochs=2, minibatches=2)
        ppo_log.attach(alg, str(self.path))
        alg.update()
        alg.update()
        r = rows(self.path)
        self.assertEqual([(x["update"], x["minibatch"]) for x in r],
                         [(u, m) for u in (0, 1) for m in range(4)])
        for x in r:
            self.assertEqual(set(x), {"update", "minibatch", "kl_mean", "clip_frac", "lr_used",
                                      "lr_after"})
            self.assertTrue(all(math.isfinite(x[k]) for k in ("kl_mean", "clip_frac", "lr_used")))

    def test_the_first_minibatch_has_no_kl_and_nothing_clipped(self):
        """Before any step the policy is the one that collected the batch."""
        alg, _, _ = stand_in()
        ppo_log.attach(alg, str(self.path))
        alg.update()
        first = rows(self.path)[0]
        self.assertAlmostEqual(first["kl_mean"], 0.0, places=12)
        self.assertEqual(first["clip_frac"], 0.0)
        self.assertGreater(rows(self.path)[-1]["kl_mean"], 0.0)

    def test_kl_and_clip_fraction_are_those_of_the_minibatch_before_its_step(self):
        alg, _, _ = stand_in(epochs=3, minibatches=1, lr=0.2)
        ppo_log.attach(alg, str(self.path))
        seen = []
        step = alg.optimizer.step                     # the hook's wrapper

        def spy(*a, **k):                             # computed by hand, before the step
            b = alg.storage._ppo_log_batch
            with torch.no_grad():
                kl = alg.actor.get_kl_divergence(b.old_distribution_params,
                                                 alg.actor.output_distribution_params).mean()
                ratio = torch.exp(alg.actor.get_output_log_prob(b.actions)
                                  - b.old_actions_log_prob.squeeze(-1))
            seen.append((float(kl), float(((ratio - 1).abs() > 0.2).float().mean())))
            return step(*a, **k)
        alg.optimizer.step = spy
        alg.update()
        r = rows(self.path)
        self.assertEqual(len(r), 3)
        for x, (kl, cf) in zip(r, seen):
            self.assertAlmostEqual(x["kl_mean"], kl, places=12)
            self.assertAlmostEqual(x["clip_frac"], cf, places=12)
        self.assertGreater(max(x["clip_frac"] for x in r), 0.0)   # lr 0.2 moves it past the clip

    def test_clip_fraction_counts_ratios_outside_the_clip(self):
        alg, obs, actions = stand_in(n=4, epochs=1, minibatches=1)
        with torch.no_grad():                         # ratios 2, 1/0.9, 1/1.1, 1/1.5
            alg.actor(obs)
            logp = alg.actor.get_output_log_prob(actions)
        r = torch.tensor([0.5, 0.9, 1.1, 1.5])
        old = (logp + torch.log(r)).unsqueeze(-1)
        gen = alg.storage.mini_batch_generator

        def fixed(*a, **k):
            for b in gen(*a, **k):
                b.old_actions_log_prob = old
                yield b
        alg.storage.mini_batch_generator = fixed
        ppo_log.attach(alg, str(self.path))
        alg.update()
        self.assertEqual(rows(self.path)[0]["clip_frac"], 0.5)

    def test_the_learning_rate_used_by_the_step_and_after_it(self):
        alg, _, _ = stand_in(schedule="adaptive", lr=1e-3, epochs=1, minibatches=2)
        ppo_log.attach(alg, str(self.path))
        alg.update()
        r = rows(self.path)
        self.assertEqual([x["lr_used"] for x in r], [5e-4, 2.5e-4])
        self.assertEqual([x["lr_after"] for x in r], [5e-4, 2.5e-4])

    def test_training_is_unchanged_bit_for_bit(self):
        """The same updates with and without the hooks: the same parameters and the same
        global RNG state after them (no extra draw), and update() returns the same."""
        out = []
        for hooked in (False, True):
            torch.manual_seed(7)
            alg, _, _ = stand_in(seed=3, epochs=3, minibatches=2, lr=0.05)
            if hooked:
                ppo_log.attach(alg, str(self.path))
            ret = [alg.update(), alg.update()]
            out.append(([p.detach().clone() for p in alg.actor.parameters()], torch.get_rng_state(), ret))
        (p0, rng0, ret0), (p1, rng1, ret1) = out
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(p0, p1)))
        self.assertTrue(torch.equal(rng0, rng1))
        self.assertEqual(ret0, ret1)
        self.assertEqual(len(rows(self.path)), 12)


def real_ppo(seed, schedule="adaptive"):
    """rsl_rl's own PPO with P4's settings (p4_leadbrake.agent: 256-128-64 ELU, normalized
    observations, init_std 1, 5 epochs x 4 minibatches, lr 1e-3, adaptive, desired_kl 0.01),
    64 envs x 24 steps of random observations and rewards, all drawn from `seed`."""
    from rsl_rl.algorithms import PPO
    from rsl_rl.models import MLPModel
    from rsl_rl.storage import RolloutStorage
    from tensordict import TensorDict
    torch.manual_seed(seed)
    n, steps, nobs, nact = 64, 24, 6, 2
    obs = TensorDict({"policy": torch.randn(n, nobs)}, batch_size=[n])
    groups = {"actor": ["policy"], "critic": ["policy"]}
    model = dict(hidden_dims=[256, 128, 64], activation="elu", obs_normalization=True)
    actor = MLPModel(obs, groups, "actor", nact, **model,
                     distribution_cfg={"class_name": "rsl_rl.modules.distribution:GaussianDistribution",
                                       "init_std": 1.0})
    critic = MLPModel(obs, groups, "critic", 1, **model)
    storage = RolloutStorage("rl", n, steps, obs, [nact], "cpu")
    alg = PPO(actor, critic, storage, num_learning_epochs=5, num_mini_batches=4, clip_param=0.2,
              value_loss_coef=1.0, use_clipped_value_loss=True, entropy_coef=0.005,
              learning_rate=1e-3, schedule=schedule, gamma=0.99, lam=0.95, desired_kl=0.01,
              max_grad_norm=1.0, device="cpu")

    def rollout():
        o = obs
        for _ in range(steps):
            alg.act(o)
            o = TensorDict({"policy": torch.randn(n, nobs)}, batch_size=[n])
            alg.process_env_step(o, torch.randn(n), torch.rand(n) < 0.02, {})
        alg.compute_returns(o)
    return alg, rollout


def has_rsl_rl():
    if torch is None:
        return False
    try:
        import rsl_rl.algorithms  # noqa: F401
        import tensordict  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(has_rsl_rl(), "no rsl_rl (the Isaac Lab venv has it)")
class RslRlTest(unittest.TestCase):
    """The hooks on rsl_rl 5.5's own PPO.update: the update is unchanged bit for bit, and its
    adaptive schedule, replayed from the logged kl_mean, gives every logged learning rate, so
    the logged KL is the one rsl_rl acted on."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ppo.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def run_updates(self, hooked, schedule="adaptive"):
        alg, rollout = real_ppo(11, schedule)
        if hooked:
            ppo_log.attach(alg, str(self.path))
        losses, lr0 = [], alg.learning_rate
        for _ in range(3):
            rollout()
            losses.append(alg.update())
        params = [p.detach().clone() for p in list(alg.actor.parameters()) + list(alg.critic.parameters())]
        return params, losses, alg.learning_rate, torch.get_rng_state(), lr0

    def test_unchanged_and_the_schedule_replays_from_the_logged_kl(self):
        p0, l0, lr0, rng0, _ = self.run_updates(False)
        p1, l1, lr1, rng1, start = self.run_updates(True)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(p0, p1)))
        self.assertEqual(l0, l1)
        self.assertEqual(lr0, lr1)
        self.assertTrue(torch.equal(rng0, rng1))
        r = rows(self.path)
        self.assertEqual([(x["update"], x["minibatch"]) for x in r],
                         [(u, m) for u in range(3) for m in range(20)])
        lr = start
        for x in r:            # rsl_rl adapts before the step: lr_used is already the new rate
            if x["kl_mean"] > 0.02:
                lr = max(1e-5, lr / 1.5)
            elif 0.0 < x["kl_mean"] < 0.005:
                lr = min(1e-2, lr * 1.5)
            self.assertAlmostEqual(x["lr_used"], lr, delta=lr * 1e-6, msg=x)
            self.assertAlmostEqual(x["lr_after"], lr, delta=lr * 1e-6, msg=x)
            self.assertTrue(0.0 <= x["clip_frac"] <= 1.0 and math.isfinite(x["kl_mean"]))
        self.assertEqual(lr, lr1)

    def test_a_fixed_schedule_logs_kl_too(self):
        self.run_updates(True, schedule="fixed")
        r = rows(self.path)
        self.assertEqual(len(r), 60)
        self.assertEqual({x["lr_used"] for x in r}, {1e-3})
        self.assertGreater(max(x["kl_mean"] for x in r), 0.0)


STAND_IN_PPO = '''
class PPO:
    def __init__(self, actor, storage, optimizer):
        self.actor, self.storage, self.optimizer = actor, storage, optimizer
        self.learning_rate, self.clip_param = 1e-3, 0.2

    def update(self):
        return "updated"
'''


class InstallTest(unittest.TestCase):
    """install() patches PPO.__init__ when rsl_rl.algorithms.ppo is imported (a stand-in
    package here, ahead of any real rsl_rl on the path), and only then; no torch needed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        pkg = root / "rsl_rl" / "algorithms"
        pkg.mkdir(parents=True)
        (root / "rsl_rl" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "ppo.py").write_text(STAND_IN_PPO)
        self.saved = {k: v for k, v in sys.modules.items() if k == "rsl_rl" or k.startswith("rsl_rl.")}
        for k in self.saved:
            del sys.modules[k]
        self.meta = list(sys.meta_path)
        sys.path.insert(0, str(root))
        self.attached = []
        self.real_attach = ppo_log.attach
        ppo_log.attach = lambda alg, path: self.attached.append((alg, path))

    def tearDown(self):
        ppo_log.attach = self.real_attach
        sys.path.remove(str(Path(self.tmp.name)))
        sys.meta_path[:] = self.meta
        for k in [k for k in sys.modules if k == "rsl_rl" or k.startswith("rsl_rl.")]:
            del sys.modules[k]
        sys.modules.update(self.saved)
        ppo_log._installed.clear()
        self.tmp.cleanup()

    def test_ppo_is_attached_when_built(self):
        ppo_log.install("/x/ppo.jsonl")
        mod = importlib.import_module("rsl_rl.algorithms.ppo")
        alg = mod.PPO("actor", "storage", "optimizer")
        self.assertEqual(self.attached, [(alg, "/x/ppo.jsonl")])
        self.assertEqual(alg.update(), "updated")
        self.assertEqual(alg.actor, "actor")

    def test_an_already_imported_ppo_is_patched_too_and_only_once(self):
        mod = importlib.import_module("rsl_rl.algorithms.ppo")
        ppo_log.install("/x/a.jsonl")
        ppo_log.install("/x/a.jsonl")
        mod.PPO(1, 2, 3)
        self.assertEqual(len(self.attached), 1)

    def test_other_modules_load_as_before(self):
        ppo_log.install("/x/ppo.jsonl")
        self.assertIs(importlib.import_module("json"), json)
        importlib.import_module("rsl_rl")
        self.assertEqual(self.attached, [])


if __name__ == "__main__":
    unittest.main()
