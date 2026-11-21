"""K2.4's batch side (roadmap 092; batch-executor.md section 8): replay one seats run in the
batch, one slot, on engine A (aib's PhysX vehicle, CPU physics) or B (the articulation), and
write the agreement table's row against the run.

    python agreement_run.py --run <seats run dir> --scenario <xosc> --world <map export .json> \\
        --map <map dir> --ego <aib ego.yaml> --commands <replay commands> [--engine A|B] \\
        [--out row.json]

The seats run is a `scensim run` of the scenario with the ego as `replay_pilot` on the same
commands; its directory holds the truth (gap_trace/), the storyboard log (context.jsonl) and
`replay_pilot.jsonl`. The batch takes S from the truth (`start_frames`), holds the ego for
`hold_steps` (the commands' start, paired by time), then steps command k at step k, with the
seats ego's onboard computers (sim_vehicle_ecu's EcuComponent for the spec's powertrain, the
ego config's `ecu` overrides). Run in the Isaac Lab overlay venv, headless, with aib,
sim_vehicle_ecu, scensim_sampler and scensim_launch's scripts on the path.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _gap_trace():
    """scensim_launch's trace reader, from this workspace's source."""
    p = HERE.parents[1] / "scensim_launch" / "scripts" / "gap_trace.py"
    spec = importlib.util.spec_from_file_location("gap_trace", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("gap_trace", mod)
    spec.loader.exec_module(mod)
    return mod


def start_frames(trace):
    """scensim.truth.start_frames, here without the scensim package (Isaac's Python)."""
    sys.path.insert(0, str(HERE.parents[1] / "scensim"))
    from scensim.truth import start_frames as sf
    return sf(trace)


def _seats_outcome(run_dir):
    """The seats run's verdict (result.json), in the batch's words: passed, failed, or
    running (SSv2's timeout)."""
    p = run_dir / "result.json"
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("verdict")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--world", required=True)
    ap.add_argument("--map", required=True, help="the map directory the run used")
    ap.add_argument("--ego", required=True)
    ap.add_argument("--commands", required=True)
    ap.add_argument("--record", default=None, help="the run's sample record (JSON); none: {}")
    ap.add_argument("--engine", choices=("A", "B"), default="A")
    ap.add_argument("--physics-dt", type=float, default=1 / 60,
                    help="the seats world server's physics step (scensim_isaac_world's "
                         "max_physics_dt, 1/60: the bridge steps a frame in substeps of it)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dump", default=None, help="both sides' poses per step, as JSON")
    a = ap.parse_args(argv)

    run_dir = Path(a.run)
    gt = _gap_trace()
    traces = sorted((run_dir / "gap_trace").glob("*.jsonl"))
    if len(traces) != 1:
        raise SystemExit(f"{run_dir}: {len(traces)} truth files, a run of one episode has one")
    trace = gt.load_trace(traces[0])
    S = start_frames(trace)
    if S is None:
        raise SystemExit(f"{traces[0]}: S cannot be read (no npc_logic_started, or a frame "
                         "before it dropped)")
    sys.path.insert(0, str(HERE.parent))
    from scensim_batch import agreement as A
    rows = A.replay_log(run_dir / "replay_pilot.jsonl")
    cmd0 = A.first_command(rows)
    if cmd0 is None:
        raise SystemExit("the replay pilot never sent command 0")
    hold = A.hold_steps(trace, S, cmd0)
    if hold is None:
        raise SystemExit(f"no truth frame at command 0's clock {cmd0['clock_ns']}")
    skipped = sum(r.get("skipped", 0) for r in rows)
    sys.path.insert(0, str(HERE.parents[1] / "scensim_agent"))
    from scensim_agent.adapters.replay_pilot import load_commands
    step_time, commands = load_commands(a.commands)
    if abs(step_time - trace.episode.step_time) > 1e-12:
        raise SystemExit(f"the commands' step {step_time} is not the run's "
                         f"{trace.episode.step_time}")
    steps = len(trace.frames) - S

    from isaaclab.app import AppLauncher
    app = AppLauncher(headless=True).app
    import torch
    from aib.rig import EgoConfig
    from scensim_batch.env import ScensimEnv, ScensimEnvCfg
    from scensim_batch.world_lanelet import LaneletWorld

    if a.engine != "A":
        raise SystemExit("engine B's environment is K2.2b's backend in ScensimEnv: not wired "
                         "into env.py yet")
    ego = EgoConfig.load(a.ego)
    rig = ego.load_rig()
    model = (rig.spec.get("powertrain") or {}).get("model", "ev")
    if model not in ("ev", "ideal"):
        raise SystemExit(f"the spec's powertrain {model!r}: the seats ego's onboard computers "
                         "have no shipped name to load in the batch")
    world = LaneletWorld.load(a.world, map_dir=a.map)
    cfg = ScensimEnvCfg()
    cfg.scenario = a.scenario
    cfg.records = [json.loads(Path(a.record).read_text()) if a.record else {}]
    cfg.world_factory = lambda: world
    cfg.rig = rig
    cfg.vehicle = rig.spec
    cfg.component = model
    cfg.component_params = dict(ego.ecu or {})
    cfg.allow_loop = True          # an agreement check, never a throughput number
    cfg.scene.num_envs = 1
    cfg.decimation = max(1, round(step_time / a.physics_dt))   # seats' substeps per frame
    cfg.sim.dt = step_time / cfg.decimation
    cfg.episode_length_s = (steps + 1) * step_time
    cfg.start_frames = S
    # the seats ego's steps up to scenario time 0, as a pre-roll of the batch ego, where the
    # truth has them (092 K2.4: its brake was held by the pilot's hold before command 0)
    hold_cmd = {"accel": -3.0, "velocity": 0.0, "steer": 0.0}
    from scensim_batch.compile import compile_scenario
    ego_entity = next(e for e in compile_scenario(a.scenario, cfg.records, world).entities
                      if e.role == "ego").name
    before = A.taken_before(trace, S, ego_entity)
    preroll = []
    if any(c is not None for c in before):
        for t in before:
            c = hold_cmd if t is None else {"accel": t.acceleration, "velocity": t.velocity,
                                            "steer": t.tire_angle}
            preroll.append([[c["accel"], c["velocity"], c["steer"]]])
        cfg.ego_preroll = preroll
    env = ScensimEnv(cfg)
    env.reset()
    rec = A.BatchRecorder(env.run)
    rec.record(env.run.obs)
    # each step's world is recorded where the env decides its dones, before Isaac Lab resets a
    # finished slot (after env.step the slot already shows its next episode's spawn)
    end = {}
    dones = env.dones

    def recording_dones():
        term, trunc = dones()
        rec.record(env.obs)
        if bool(term[0]) and "outcome" not in end:
            end["outcome"], end["step"] = env.run.outcome()[0], rec.k - 1
        return term, trunc

    env.dones = recording_dones
    ego_name = env.compiled.entities[env.run.ego].name
    # what the seats ego ran, frame by frame, where the truth has it (092 K2.4): the batch
    # replays that, and the delivery (delays, superseded and repeated commands) is its own
    # column; else the commands as sent, from the hold on
    taken = A.taken_commands(trace, S, steps, ego_name)
    replay = "taken" if any(c is not None for c in taken) else "sent"
    for k in range(steps - 1):
        if replay == "taken":
            # the step to frame S + k + 1 ran that frame's command (the record at k + 1)
            t = taken[k + 1]
            c = hold_cmd if t is None else {"accel": t.acceleration, "velocity": t.velocity,
                                             "steer": t.tire_angle}
        else:
            # command k - hold at step k: a negative hold (the pilot started before
            # startNpcLogic) starts the batch -hold commands in
            i = k - hold
            c = hold_cmd if i < 0 else commands[min(i, len(commands) - 1)]
        act = torch.tensor([[c["accel"], c["velocity"], c["steer"]]])
        env.step(act)
        if end:
            break
    outcome = end.get("outcome", env.run.outcome()[0])
    entities = [e.name for e in env.compiled.entities]
    seats = {"poses": A.seats_poses(trace, S, steps, entities,
                                    pose={n: ("sim" if n == ego_name else "ssv2")
                                          for n in entities}),
             "steps": A.context_steps(run_dir / "context.jsonl", step_time)
             if (run_dir / "context.jsonl").exists() else {},
             "outcome": _seats_outcome(run_dir)}
    batch = {"poses": rec.poses, "steps": rec.steps,
             "outcome": {"success": "passed", "failure": "failed"}.get(outcome, outcome)}
    if a.dump:
        Path(a.dump).write_text(json.dumps({"seats": seats["poses"], "batch": batch["poses"]}))
    row = {"scenario": Path(a.scenario).name, "engine": a.engine, "S": S, "hold_steps": hold,
           "skipped_frames": skipped, "steps": steps, "batch_end_step": end.get("step"),
           "replay": replay, "preroll_steps": len(preroll),
           "delivery": A.delivery(trace, ego_name, step_time) if replay == "taken" else None,
           **A.compare(seats, batch)}
    text = json.dumps(row, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text, flush=True)
    env.close()
    app.close()


if __name__ == "__main__":
    main()
