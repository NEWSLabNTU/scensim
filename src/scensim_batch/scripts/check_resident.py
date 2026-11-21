"""092 K2.2c: engine B through ScensimEnv, device-resident against the CPU path (the reference).

    python check_resident.py --body <articulation.yaml> --spec <spec.yaml> [--resident] \\
        --out run.json [--n 4]

One process per run (Isaac Sim's app): the RoboRacer alone on a straight track, its VESC
component (roboracer_vesc) on a fixed plan of speed and servo commands, the GPU sim, 1/200 s
physics and 4 substeps (50 Hz, 094 P2's rates); per step the ego's x, y, yaw, v and the
outcome. `--resident`: BatchRun, the car model and the component on the GPU (array_api
torch), else on the CPU with the component on numpy. Run both, then
`check_resident.py --compare a.json b.json`. Run in the Isaac Lab venv, headless, with
sim_vehicle_ecu, scensim_sampler and roboracer_vesc on the path.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def plan(k):
    """ERPM and servo per step: up to 6000 ERPM, a left then a right, a brake to 0."""
    erpm = 6000.0 if k < 200 else 0.0
    servo = 0.5304 + (0.2 if 60 <= k < 120 else -0.2 if 120 <= k < 160 else 0.0)
    return erpm, servo


def run(a):
    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=True, device="cuda:0").app
    import torch
    import yaml
    sys.path.insert(0, str(HERE.parent))
    from scensim_batch.env import ScensimEnv, ScensimEnvCfg
    from scensim_batch.world_lanelet import LaneletWorld

    spec = yaml.safe_load(Path(a.spec).read_text())
    world = LaneletWorld.from_polylines({1: [[0.0, 0.0], [200.0, 0.0]]}, width=3.0)
    cfg = ScensimEnvCfg()
    cfg.scenario = str(HERE / "check_resident.xosc")
    cfg.records = [{}] * a.n
    cfg.world_factory = lambda: world
    cfg.vehicle = spec
    from roboracer_vesc.component import RoboRacerVesc
    cfg.component = RoboRacerVesc
    cfg.vesc_mode = "speed"
    cfg.engine, cfg.body = "B", a.body
    cfg.device_resident = a.resident
    cfg.scene.num_envs = a.n
    cfg.scene.env_spacing = 10.0
    cfg.sim.device = "cuda:0"
    cfg.sim.dt = 1 / 200
    cfg.decimation = 4
    cfg.episode_length_s = 7.0
    cfg.action_space = 2
    env = ScensimEnv(cfg)
    env.reset()
    rows, t0 = [], time.perf_counter()
    steps = 290
    for k in range(steps):
        erpm, servo = plan(k)
        act = torch.tensor([[erpm, servo]] * a.n, device=env.device)
        env.step(act)
        o = env.run.obs
        e = env.run.ego
        rows.append({f: o[f][:, e].detach().cpu().double().tolist() for f in ("x", "y", "yaw", "v")}
                    | {"outcome": env.run.outcome()})
    dt = time.perf_counter() - t0
    out = {"resident": a.resident, "n": a.n, "ms_per_step": 1e3 * dt / steps,
           "device_of_obs": str(env.run.obs["x"].device), "rows": rows}
    Path(a.out).write_text(json.dumps(out))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}), flush=True)
    env.close()
    app.close()


def compare(pa, pb):
    a, b = (json.loads(Path(p).read_text()) for p in (pa, pb))
    worst = {f: 0.0 for f in ("x", "y", "yaw", "v")}
    for ra, rb in zip(a["rows"], b["rows"]):
        for f in worst:
            worst[f] = max(worst[f], max(abs(p - q) for p, q in zip(ra[f], rb[f])))
        assert ra["outcome"] == rb["outcome"], (ra["outcome"], rb["outcome"])
    print(json.dumps({"steps": len(a["rows"]), "max_abs": worst,
                      "ms_per_step": [a["ms_per_step"], b["ms_per_step"]],
                      "final_x": [a["rows"][-1]["x"][0], b["rows"][-1]["x"][0]]}))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--body")
    ap.add_argument("--spec")
    ap.add_argument("--resident", action="store_true")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--out")
    ap.add_argument("--compare", nargs=2)
    a = ap.parse_args(argv)
    if a.compare:
        compare(*a.compare)
    else:
        run(a)


if __name__ == "__main__":
    main()
