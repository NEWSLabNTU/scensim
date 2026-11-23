"""094 P2's pass bar on scensim's drift task: stock's bench/p1/eval_drift.py (WheeledLab fork,
isaaclab-3.0, 241's) with the env ours and nothing else changed. A trained policy,
deterministic, N envs for T seconds of sim time, on the run's own training configuration (its
observation noise, perturbations and randomisation, its row and start distribution), with the
off-track termination and its penalty off, the curriculum off and the episode longer than T.

The bar, the laps, the spin-out and the controlled slip are stock's code's, word for word:

- laps: the unwrapped angle of the car's position about the oval's centre, over 2 pi;
- off track: the task's own test (DriftEnv.off_track, stock's cart_off_track), at any step;
- spin-out: slip above 100 deg, or moving clockwise, for 0.5 s on end, above 0.5 m/s;
- peak controlled slip: the largest slip on track, not spun out, counter-clockwise, v_x > 0.5;
- mean speed: the planar speed's mean over the run.

A policy passes when at least 90 % of envs complete 3 laps clean, the median peak controlled
slip is at least 40 deg and the mean speed at least 1.2 m/s.

    python eval_drift.py --run-path <run dir> [--checkpoint N] [--envs 32] [--seconds 30] \\
        [--row b|a] [--starts stock|uniform] --out <json>

Run it as train_drift.py runs train_rl.py: from the WheeledLab checkout, with its source/*
packages, scensim_batch and its dependencies on the path, SCENSIM_ASSET_ROOT set.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wheeledlab_rl.startup import startup  # noqa: E402

parser = argparse.ArgumentParser(description="094 P2: the drift policy's pass bar, ours.")
parser.add_argument("--run-path", required=True)
parser.add_argument("--checkpoint", type=int, default=None, help="default: the last")
parser.add_argument("--envs", type=int, default=32)
parser.add_argument("--seconds", type=float, default=30.0)
parser.add_argument("--row", choices=("a", "b"), default="b")
parser.add_argument("--starts", choices=("stock", "uniform"), default="stock")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--out", required=True)
simulation_app, args_cli = startup(parser=parser)
from aib import app_exit  # noqa: E402

app_exit.guard(simulation_app)  # an escaped exception ends with 1, not Kit's 0 (scensim issue 118)

import glob  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from importlib import metadata  # noqa: E402

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402
from wheeledlab_rl.utils import ClipAction  # noqa: E402

__import__("scensim_batch.tasks")   # registers Scensim-MushrDriftRL-v0
from scensim_batch.tasks.drift import MushrDriftRLEnvCfg  # noqa: E402

TASK = "Scensim-MushrDriftRL-v0"
ROW_A = "roboracer_vesc.component:RoboRacerVesc"
BAR = dict(laps=3.0, share_clean=0.90, slip_deg=40.0, speed=1.2)        # stock's
SPIN_SLIP = math.radians(100.0)
SPIN_HOLD_S = 0.5
MIN_SPEED = 0.5


def checkpoint(run_path, n):
    models = glob.glob(os.path.join(run_path, "models", "model_*.pt"))
    if not models:
        raise SystemExit(f"no checkpoints in {run_path}/models")
    by_it = {int(re.search(r"model_(\d+)\.pt$", m).group(1)): m for m in models}
    it = max(by_it) if n is None else n
    return it, by_it[it]


def main():
    from isaaclab_tasks.utils.parse_cfg import load_cfg_from_registry
    agent_cfg = load_cfg_from_registry(TASK, "rsl_rl_cfg_entry_point")
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, metadata.version("rsl-rl-lib"))
    it, path = checkpoint(args_cli.run_path, args_cli.checkpoint)

    env_cfg = MushrDriftRLEnvCfg()
    env_cfg.num_envs = env_cfg.scene.num_envs = args_cli.envs
    env_cfg.seed = args_cli.seed
    env_cfg.starts = args_cli.starts
    env_cfg.drift_component = ROW_A if args_cli.row == "a" else ""
    env_cfg.terminate_off_track = False                 # counted here instead
    env_cfg.curriculum = False                          # fixed reward weights
    env_cfg.episode_length_s = args_cli.seconds + 5.0   # no time-out inside the window
    env_cfg.resolve()
    env = gym.make(TASK, cfg=env_cfg)
    env.unwrapped.weights["term_pens"] = 0.0            # it reads that termination
    env.action_space.low, env.action_space.high = -1.0, 1.0
    env = RslRlVecEnvWrapper(ClipAction(env))
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=env.unwrapped.device)
    runner.load(path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    u = env.unwrapped
    dt = u.step_dt
    steps = int(round(args_cli.seconds / dt))
    n, dev = u.num_envs, u.device
    hold = max(1, int(round(SPIN_HOLD_S / dt)))

    def planar():
        return u._root()[0][:, :2].float()

    obs = env.get_observations()
    p0 = planar()
    ang_prev = torch.atan2(p0[:, 1], p0[:, 0])
    ang_total = torch.zeros(n, device=dev)
    off = torch.zeros(n, dtype=torch.bool, device=dev)
    spun = torch.zeros(n, dtype=torch.bool, device=dev)
    bad_run = torch.zeros(n, dtype=torch.long, device=dev)
    peak_slip = torch.zeros(n, device=dev)
    speed_sum = torch.zeros(n, device=dev)
    with torch.inference_mode():
        for _ in range(steps):
            obs, _, _, _ = env.step(policy(obs))
            p = planar()
            ang = torch.atan2(p[:, 1], p[:, 0])
            d = torch.remainder(ang - ang_prev + math.pi, 2 * math.pi) - math.pi
            ang_total += d
            ang_prev = ang
            v = u._root()[2][:, :2].float()
            speed = torch.linalg.norm(v, dim=-1)
            speed_sum += speed
            slip = torch.abs(torch.atan2(v[:, 1], v[:, 0]))
            backwards = d < 0
            bad = (speed > MIN_SPEED) & ((slip > SPIN_SLIP) | backwards)
            bad_run = torch.where(bad, bad_run + 1, torch.zeros_like(bad_run))
            spun |= bad_run >= hold
            off |= u.off_track()
            controlled = (~off) & (~spun) & (~backwards) & (v[:, 0] > MIN_SPEED)
            peak_slip = torch.maximum(peak_slip,
                                      torch.where(controlled, slip, torch.zeros_like(slip)))

    laps = (ang_total / (2 * math.pi)).cpu()
    off, spun = off.cpu(), spun.cpu()
    clean = (laps >= BAR["laps"]) & ~off & ~spun
    slip_deg = torch.rad2deg(peak_slip).cpu()
    mean_speed = (speed_sum / steps).cpu()
    res = dict(
        run_path=os.path.abspath(args_cli.run_path), checkpoint=it, envs=n,
        seconds=args_cli.seconds, step_dt=dt, bar=BAR, row=args_cli.row, starts=args_cli.starts,
        share_clean=float(clean.float().mean()), laps_median=float(laps.median()),
        laps_min=float(laps.min()), off_track=int(off.sum()), spun=int(spun.sum()),
        slip_deg_median=float(slip_deg.median()), slip_deg_max=float(slip_deg.max()),
        speed_mean=float(mean_speed.mean()),
        per_env=dict(laps=laps.tolist(), off=off.tolist(), spun=spun.tolist(),
                     slip_deg=slip_deg.tolist(), speed=mean_speed.tolist()),
    )
    res["passed"] = bool(res["share_clean"] >= BAR["share_clean"]
                         and res["slip_deg_median"] >= BAR["slip_deg"]
                         and res["speed_mean"] >= BAR["speed"])
    os.makedirs(os.path.dirname(os.path.abspath(args_cli.out)), exist_ok=True)
    with open(args_cli.out, "w") as f:
        json.dump(res, f, indent=1)
    print("EVAL", json.dumps({k: v for k, v in res.items() if k != "per_env"}))
    env.close()


if __name__ == "__main__":
    app_exit.run(main)
    simulation_app.close()
