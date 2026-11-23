"""094 P4's pass bar on scensim's lead-brake task: stock's bench/p4_leadbrake/tools/evaluate.py
(WheeledLab fork, isaaclab-3.0, fef6385) with the env ours and nothing else changed. One episode
in each of N conditions (env.reset()'s first episodes: here the start pool's first N records at a
fixed seed, stock's its own draws at its seed, the same distribution), judged by the task's own
terms. An episode succeeds with no collision and no lane exit, and either the route's end or a
safe stop behind the stopped lead (at rest, a gap of 2 to 8 m) at time-out. A checkpoint passes
at >= 95 % successes. The end reason is the first of collided, off_road, route_done, time_out
that holds, in stock's order.

    python eval_leadbrake.py --checkpoint <model_N.pt> [--conditions 256] [--seed 20261122] \\
        [--out <json>]

Run it as stock's: Isaac Lab's Python, with scensim_batch and its dependencies, and stock's
bench/p4_leadbrake (its PPO settings, which Scensim-LeadBrake-v0 names) on the path.
Prints one JSON line, as stock's, with the conditions' records named.
"""
import argparse
import json
import os

from isaaclab.app import AppLauncher

ap = argparse.ArgumentParser(description="094 P4: the lead-brake policy's pass bar, ours.")
ap.add_argument("--checkpoint", required=True)
ap.add_argument("--conditions", type=int, default=256)
ap.add_argument("--seed", type=int, default=20261122)
ap.add_argument("--out", default="")
ap.add_argument("--row", choices=("joints", "ecu"), default="joints")
ap.add_argument("--engine", choices=("B", "A"), default="B")
ap.add_argument("--conditions-from", default="",
                help="stock's evaluator's --samples-out file: its episodes, replayed in env order "
                     "(their count is the conditions'), and each paired with stock's outcome")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
app = AppLauncher(args).app
from aib import app_exit  # noqa: E402

app_exit.guard(app)  # an exception that escapes ends with 1, not with Kit's 0 (scensim issue 118)

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
from isaaclab.utils.seed import configure_seed  # noqa: E402
from isaaclab_rl.rsl_rl import (RslRlVecEnvWrapper, check_rsl_rl_version,  # noqa: E402
                                create_rsl_rl_runner, handle_deprecated_rsl_rl_cfg)
from isaaclab_tasks.utils.parse_cfg import load_cfg_from_registry  # noqa: E402

__import__("scensim_batch.tasks")                    # registers Scensim-LeadBrake-v0
from scensim_batch.tasks import leadbrake as LB  # noqa: E402
from scensim_batch.tasks.leadbrake_env import LeadBrakeEnvCfg  # noqa: E402

TASK = "Scensim-LeadBrake-v0"
BAR = 0.95                                                           # stock's
REASONS = ("collided", "off_road", "route_done", "time_out")         # stock's order


def main():
    agent_cfg = load_cfg_from_registry(TASK, "rsl_rl_cfg_entry_point")
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, check_rsl_rl_version())
    n = args.conditions
    stock_eps = None
    if args.conditions_from:
        _, doc = LB.records_from_samples(args.conditions_from)
        stock_eps = doc["episodes"]
        n = len(stock_eps)
    env_cfg = LeadBrakeEnvCfg(num_envs=n)
    env_cfg.seed = args.seed
    env_cfg.pool_seed = args.seed            # the conditions: the pool's first n records
    env_cfg.conditions_from = args.conditions_from    # or stock's episodes, in its env order
    env_cfg.train_headway = "record"         # the evaluation is at h exactly, as stock's
    env_cfg.row, env_cfg.engine_name = args.row, args.engine
    env_cfg.__post_init__()
    configure_seed(args.seed)
    env = RslRlVecEnvWrapper(gym.make(TASK, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    runner = create_rsl_rl_runner(env, agent_cfg)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=env.unwrapped.device)
    u = env.unwrapped
    first = {}
    for line in u.start_log:                 # env.reset()'s: each slot's first record
        if "slot" in line and line["slot"] not in first:
            first[line["slot"]] = line
    recs = [u.pool.record(first[i]["row"]) for i in range(n)]
    cond = [LB.episode_from_record(r["values"]) for r in recs]
    done = torch.zeros(n, dtype=torch.bool, device=u.device)
    why = [None] * n
    ok = torch.zeros(n, dtype=torch.bool, device=u.device)
    end_gap = torch.zeros(n, device=u.device)
    end_y = torch.zeros(n, device=u.device)
    obs = env.get_observations()
    with torch.inference_mode():
        while not bool(done.all()):
            obs, _, dones, _ = env.step(policy(obs))
            new = dones.bool() & ~done
            if bool(new.any()):
                oc = u.outcome                       # the step's terms, before its resets
                terms = {"collided": oc["collided"], "off_road": oc["off_road"],
                         "route_done": oc["route_done"], "time_out": u.time_out}
                for i in new.nonzero().flatten().tolist():
                    why[i] = next((t for t in REASONS if bool(terms[t][i])), "other")
                    ok[i] = (why[i] == "route_done") or \
                        (why[i] == "time_out" and bool(oc["safe"][i]))
                    end_gap[i], end_y[i] = oc["gap"][i], oc["y"][i]
                done |= new
    reasons = {}
    for w in why:
        reasons[w] = reasons.get(w, 0) + 1
    rate = float(ok.float().mean())
    keys = ("lead_speed", "headway", "decel", "onset")
    res = {
        "checkpoint": args.checkpoint, "conditions": n, "seed": args.seed,
        "row": args.row, "engine": args.engine,
        "successes": int(ok.sum()), "success_rate": round(rate, 4), "pass": rate >= BAR,
        "end_reasons": reasons,
        "end_gap_m": {"min": round(float(end_gap.min()), 2),
                      "median": round(float(end_gap.median()), 2)},
        "end_abs_y_m": {"max": round(float(end_y.abs().max()), 2)},
        "conditions_sampled": {k: [round(min(c[k] for c in cond), 2),
                                   round(max(c[k] for c in cond), 2)] for k in keys},
        "records": [r["id"] for r in recs],
    }
    if stock_eps is not None:                # the same episodes: paired, one by one
        for k, (c, e) in enumerate(zip(cond, stock_eps)):
            if any(abs(c[key] - float(e[key])) > 1e-6 for key in LB.KEYS):
                raise SystemExit(f"episode {k}: replayed {c}, stock's {e}")
        st = [bool(e["success"]) for e in stock_eps]
        ours = ok.tolist()
        res["conditions_from"] = os.path.abspath(args.conditions_from)
        res["paired"] = {
            "both": sum(a and b for a, b in zip(ours, st)),
            "ours_only": sum(a and not b for a, b in zip(ours, st)),
            "stock_only": sum(b and not a for a, b in zip(ours, st)),
            "neither": sum(not a and not b for a, b in zip(ours, st)),
            "stock_successes": sum(st)}
    print(json.dumps({k: v for k, v in res.items() if k != "records"}), flush=True)
    if args.out:
        res["per_env"] = {"ok": ok.tolist(), "why": why, "end_gap": end_gap.tolist(),
                          "end_y": end_y.tolist(), "conditions": cond}
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(res, f, indent=1)
    env.close()


if __name__ == "__main__":
    app_exit.run(main)
    app.close()
