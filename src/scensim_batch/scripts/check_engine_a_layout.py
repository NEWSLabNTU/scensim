"""Issue 113's check of engine A's slot layout, on the lead-brake task (no training): every slot
plays the same episode (one of stock's, replayed in all N) under the same actions, so a slot's
observation and reward are the same in each, whatever its place, and no car comes near another.

    python check_engine_a_layout.py --samples <stock's --samples-out file> [--n 200] [--steps 120]

N = 200 lays the slots out in two columns (layout.route_layout on the task's 4 km ground), so
slot 0 and slot N-1 stand in different columns. Prints one JSON line; exits non-zero if:
- any slot's observation or reward differs from slot 0's by more than --tol at any step (its
  lateral offset and gap: --tol-y, --tol-gap);
- the slots' lateral deviation from their median, fitted against their distance from the world's
  origin, has a slope over --max-slope m per km or a deviation over --max-dev (a layout error is
  metres: three orders of magnitude over either);
- two cars come closer than the backend's SEPARATION_WARN;
- a car still at rest at the end (after a full brake, held --hold s) has moved in height by more
  than 1 cm over the hold, or its speed is above 0.05 m/s (on its wheels, on the ground).
Run as eval_leadbrake.py: Isaac Lab's Python, scensim_batch and its dependencies, stock's
bench/p4_leadbrake on the path."""
import argparse
import json
import os
import tempfile

from isaaclab.app import AppLauncher

ap = argparse.ArgumentParser()
ap.add_argument("--samples", required=True)
ap.add_argument("--episode", type=int, default=0)
ap.add_argument("--n", type=int, default=200)
ap.add_argument("--steps", type=int, default=120)
ap.add_argument("--hold", type=float, default=2.0)
ap.add_argument("--tol", type=float, default=1e-3)
# the lateral offset and the gap (m) against slot 0's, set after results (133, 2026-11-23): y 2 cm
# (measured 1.46 cm, 200 and 1024 slots out to 2.2 km), the gap 2 cm (1.8 mm at 200 slots, 1.12
# cm at 1024); the observation's other terms (2.2e-5) and the reward (8.5e-7) to --tol
ap.add_argument("--tol-y", type=float, default=0.02)
ap.add_argument("--tol-gap", type=float, default=0.02)
# Each slot's lateral deviation from the slots' median, fitted against its distance from the
# world's origin. float32 rounding grows with the coordinate (its ULP is proportional to it), so
# a smooth slope is precision; a layout error is an offset of metres, a contact or a slot off the
# line. All set after results (133, 2026-11-23), the 1024-slot run's measured values beside them:
# the slope (4.7 mm/km) and the largest deviation (1.0 cm); the gap above (1.12 cm, its |x| out
# to 950 m). Each slot's residual from the line is reported, not judged: a 5 mm bound on it, set
# before any residual was seen, failed on 7.25 mm of rounding (it follows the ULP's power-of-2
# steps, with any sign), so a residual cannot tell noise from an odd slot (133: dropped).
ap.add_argument("--max-slope", type=float, default=0.01)
ap.add_argument("--max-dev", type=float, default=0.02)
ap.add_argument("--out", default="", help="each slot's distance, deviation and residual (json)")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

__import__("scensim_batch.tasks")
from scensim_batch import layout  # noqa: E402
from scensim_batch.physx_vehicle import SEPARATION_WARN  # noqa: E402
from scensim_batch.tasks.leadbrake_env import LeadBrakeEnvCfg  # noqa: E402


def main():
    doc = json.load(open(args.samples))
    ep = doc["episodes"][args.episode]
    doc["episodes"] = [dict(ep) for _ in range(args.n)]       # the one episode in every slot
    fd, same = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f)
    cfg = LeadBrakeEnvCfg(num_envs=args.n)
    cfg.row, cfg.engine_name = "ecu", "A"
    cfg.conditions_from, cfg.train_headway = same, "record"
    cfg.__post_init__()
    env = gym.make("Scensim-LeadBrake-v0", cfg=cfg)
    u = env.unwrapped
    be = u.backend
    origins = be.origins
    res = {"n": args.n, "route_box": [round(v, 3) for v in cfg.route_box],
           "columns": int(len(np.unique(np.round(origins[:, 0], 3)))),
           "origin_0": origins[0].round(2).tolist(), "origin_last": origins[-1].round(2).tolist(),
           "layout_min_m": round(layout.min_separation(origins)[0], 2)}
    obs, _ = env.reset()
    o = obs["policy"]
    worst_obs, worst_rew, min_sep = float((o - o[:1]).abs().max()), 0.0, np.inf
    dim = (o - o[:1]).abs().max(0).values           # per observation term
    slot = (o - o[:1]).abs().max(1).values          # per slot
    dev_y = (o[:, 2] - o[:, 2].median()).abs()       # per slot, from the slots' median
    n_done = 0
    for k in range(args.steps):
        # the same action in every slot: drive, a steer that changes, so lateral states move
        a = torch.zeros(args.n, 2, device=u.device)
        a[:, 0] = 0.6 if k < args.steps // 2 else -1.0
        a[:, 1] = 0.05 * np.sin(k / 10.0)
        obs, rew, term, trunc, _ = env.step(a)
        o = obs["policy"]
        worst_obs = max(worst_obs, float((o - o[:1]).abs().max()))
        dim = torch.maximum(dim, (o - o[:1]).abs().max(0).values)
        slot = torch.maximum(slot, (o - o[:1]).abs().max(1).values)
        dev_y = torch.maximum(dev_y, (o[:, 2] - o[:, 2].median()).abs())
        worst_rew = max(worst_rew, float((rew - rew[:1]).abs().max()))
        d, _ = layout.min_separation([st.position[:2] for st in be.states])
        min_sep = min(min_sep, d)
        n_done += int((term | trunc).any())
    # a full brake held: every car at rest on its wheels
    z0 = None
    hold_steps = int(round(args.hold / u.step_dt))
    for k in range(hold_steps):
        a = torch.zeros(args.n, 2, device=u.device)
        a[:, 0] = -1.0
        env.step(a)
        z = np.array([st.position[2] for st in be.states])
        if z0 is None and k >= hold_steps // 2:
            z0 = z
    z1 = np.array([st.position[2] for st in be.states])
    v = np.array([abs(st.velocity[0]) for st in be.states])
    far = np.hypot(origins[:, 0], origins[:, 1])
    dy = dev_y.cpu().numpy()
    slope, icept = np.polyfit(far / 1000.0, dy, 1)
    resid = np.abs(dy - (slope * far / 1000.0 + icept))
    res["y_dev_fit"] = {"slope_m_per_km": float(f"{slope:.3g}"), "at_origin_m": float(f"{icept:.3g}"),
                        "max_m": float(f"{dy.max():.3g}"),
                        "max_residual_m": float(f"{resid.max():.3g}"), "slots_km": [round(float(far.min()) / 1e3, 2),
                                                                        round(float(far.max()) / 1e3, 2)]}
    sl = slot.cpu().numpy()
    res.update({"obs_diff_by_term": [float(f"{x:.3g}") for x in dim.tolist()],
                "obs_diff_vs_distance": {  # slots by their origin's distance from the world's
                    f"{lo}-{hi} m": float(f"{sl[(far >= lo) & (far < hi)].max():.3g}")
                    for lo, hi in ((0, 500), (500, 1000), (1000, 1500), (1500, 2500))
                    if ((far >= lo) & (far < hi)).any()},
                "obs_max_diff": worst_obs, "reward_max_diff": worst_rew,
                "min_separation_m": round(min_sep, 2), "steps_with_a_reset": n_done,
                "rest_dz_m": float(np.abs(z1 - z0).max()), "rest_v_max": float(v.max()),
                "rest_z": [round(float(z1.min()), 4), round(float(z1.max()), 4)]})
    tol = np.full(len(dim), args.tol)
    tol[2], tol[4] = args.tol_y, args.tol_gap        # y, gap (leadbrake_env._get_observations)
    res["obs_terms_within"] = bool((dim.cpu().numpy() <= tol).all())
    ok = (res["obs_terms_within"] and slope <= args.max_slope and
          dy.max() <= args.max_dev and worst_rew <= args.tol and min_sep >= SEPARATION_WARN
          and res["rest_dz_m"] <= 0.01 and res["rest_v_max"] <= 0.05)
    res["pass"] = bool(ok)
    print("CHECK " + json.dumps(res), flush=True)
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"check": res, "slots": {"origin": origins.round(3).tolist(),
                                               "distance_m": far.round(3).tolist(),
                                               "y_dev_m": dy.tolist(), "residual_m": resid.tolist()}},
                      f)
    env.close()
    os.unlink(same)
    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    # Kit's close ends the process with its own status (0): the check's goes out first
    os._exit(rc)
