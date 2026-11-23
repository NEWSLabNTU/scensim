"""094 P2's drift task, a smoke: DriftEnv on the MuSHR (its asset), the start pool, stock's
terms; random actions for a few seconds. Prints the step time, the terms' means, the episodes
ended and the pool's numbers. Run in the Isaac Lab venv, headless:

    python smoke_drift.py --spec src/sim_vehicle_spec/vehicles/mushr_nano.yaml --asset-root <WheeledLab source/> \\
        --dist <mushr_drift_dist.xosc> [--n 64] [--steps 300] [--log starts.jsonl]
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from aib import app_exit

HERE = Path(__file__).resolve().parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--asset-root", required=True)
    ap.add_argument("--dist", required=True)
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--log", default="")
    ap.add_argument("--no-randomize", action="store_true")
    a = ap.parse_args(argv)
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=True, device="cuda:0").app
    app_exit.guard(app)  # an escaped exception ends with 1, not with Kit's 0 (scensim issue 118)
    import torch
    sys.path.insert(0, str(HERE.parent))
    from sim_vehicle_spec import articulation as gen, spec as specmod
    from scensim_batch.tasks.drift import DriftEnv, DriftEnvCfg
    from scensim_batch.world_lanelet import LaneletWorld

    sp = specmod.load(a.spec)
    body = os.path.join(tempfile.mkdtemp(prefix="mushr_"), "articulation.yaml")
    Path(body).write_text(gen.files(sp, "smoke_drift")["articulation.yaml"])
    world = LaneletWorld.from_polylines({1: [[0.8, -0.8], [0.8, 0.8]]}, width=4.0)
    cfg = DriftEnvCfg()
    cfg.randomize = not a.no_randomize
    cfg.__post_init__()
    cfg.world_factory = lambda: world
    cfg.vehicle = sp.doc
    cfg.component = "ideal"
    cfg.body, cfg.asset_root = body, a.asset_root
    cfg.start_pool = {"distribution": a.dist, "seed": 7, "chunk": max(4 * a.n, 1000),
                      "run_knobs": "scensim_batch.tasks.drift_start:reference_points",
                      "log": a.log}
    cfg.scene.num_envs = a.n
    cfg.sim.device = "cuda:0"
    env = DriftEnv(cfg)
    obs, _ = env.reset()
    ends, t0 = 0, time.perf_counter()
    sums = {}
    for k in range(a.steps):
        act = torch.rand(a.n, 2, device=env.device) * 2 - 1
        act[:, 0] = act[:, 0].abs()
        obs, rew, term, trunc, extras = env.step(act)
        ends += int((term | trunc).sum())
        for name, v in env._terms().items():
            sums[name] = sums.get(name, 0.0) + float(v.float().mean())
    dt = time.perf_counter() - t0
    out = {"n": a.n, "steps": a.steps, "ms_per_step": 1e3 * dt / a.steps, "episodes_ended": ends,
           "obs_dim": int(obs["policy"].shape[-1]), "obs_finite": bool(torch.isfinite(obs["policy"]).all()),
           "reward_finite": bool(torch.isfinite(rew).all()),
           "term_means": {k: round(v / a.steps, 4) for k, v in sums.items()},
           "weights": env.weights, "pool": env.pool.stats(), "starts_logged": len(env.start_log)}
    print("SMOKE_DRIFT", json.dumps(out), flush=True)
    env.close()
    app.close()


if __name__ == "__main__":
    app_exit.run(main)
