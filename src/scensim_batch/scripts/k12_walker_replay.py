"""K12's exit check 2 (docs/roadmap/092, "K12's exit runs"): a seats run's commanded walker
against the batch's model on the same record, replayed on the run's own ego truth.

    python3 k12_walker_replay.py --run <run dir> --map <map dir> [--project <dir>] \
        [--entity walker] [--out f.json]

The model is built as the seats runner builds it (scensim.behaviour.seats.build: the scenario
compiled for the run's record, anchors by scensim_batch.core.model_anchors), and stepped as the
batch steps it: on its own state from the walker's Init pose, moved by
scensim_batch.core.model_law, fed each frame the seats ego's truth (pose, velocity, and the
acceleration differenced over the frame's sim time, as the runner does). Frames pair as the lag
does, by the truth's own cmd_frame: the walker's truth at frame j was moved by the command that
answered the truth frame whose sim_frame is j's cmd_frame, so it is compared with the replay's
state after its step on that frame. The comparison is in x and y (the world puts the walker's z
on the ground). The model's events are compared with the run's decisions.jsonl by frame.

Prints one JSON object: the largest xy error and its frame, the frames compared, the events on
each side and whether they match. System Python with ROS 2 (lanelet2, scensim, scensim_batch,
sim_vehicle_ecu and scensim_launch's scripts importable).
"""
import argparse
import json
import math
import sys
from pathlib import Path


def ego_inputs(trace, ego):
    """Per truth frame: (frame, sim_frame, dt, ego (x, y, vx, vy, ax, ay)) as the runner
    computed them, or ego None where the ego is absent."""
    out, prev_t, prev_v = [], None, None
    for f in trace.frames:
        t = f.sim_time_ns
        dt = (t - prev_t) / 1e9 if t is not None and prev_t is not None and t > prev_t else None
        prev_t = t if t is not None else prev_t
        s = f.entities.get(ego)
        e = None
        if s is not None and s.sim_pose is not None:
            vx, vy = s.velocity[0], s.velocity[1]
            ax, ay = ((0.0, 0.0) if prev_v is None or dt is None else
                      ((vx - prev_v[0]) / dt, (vy - prev_v[1]) / dt))
            prev_v = (vx, vy)
            e = (s.sim_pose.x, s.sim_pose.y, vx, vy, ax, ay)
        out.append((f.frame, f.sim_frame, dt, e))
    return out


def replay(trace, model, entity, ego, x0, y0, step_time=0.05, events=None):
    """The comparison (module doc): `model` one slot on numpy, `x0, y0` the walker's Init
    pose, `events` {frame: event name} from the run's decisions.jsonl."""
    import numpy as np
    import torch
    from scensim.behaviour.walker import EVENTS
    from scensim_batch.core import model_law

    a = lambda v: np.array([float(v)])        # noqa: E731
    t = lambda v: torch.tensor([float(v)], dtype=torch.float64)   # noqa: E731
    x, y, v = t(x0), t(y0), t(0.0)
    after = {}                                # sim_frame -> replay (x, y) after that frame's step
    mine = {}
    present = {f.frame: f.entities.get(entity) for f in trace.frames}
    for frame, sim_frame, dt, e in ego_inputs(trace, ego):
        if e is None or present.get(frame) is None or present[frame].sim_pose is None:
            continue
        dt = dt or step_time
        obs = {"x": a(x), "y": a(y), "ego_x": a(e[0]), "ego_y": a(e[1]), "ego_vx": a(e[2]),
               "ego_vy": a(e[3]), "ego_ax": a(e[4]), "ego_ay": a(e[5]), "valid": np.array([True])}
        act, ev = model.step(obs, dt)
        k = int(np.asarray(ev)[0])
        if k:
            mine[frame] = EVENTS.get(k, str(k))
        x, y, v = model_law(x, y, v, t(act["speed"][0]), t(act["heading"][0]),
                            t(act["accel_limit"][0]), dt)
        after[sim_frame] = (float(x), float(y))
    worst, at, compared = 0.0, None, 0
    for f in trace.frames:
        s = f.entities.get(entity)
        if s is None or s.sim_pose is None or not s.cmd_frame:
            continue
        r = after.get(s.cmd_frame)
        if r is None:
            continue
        err = math.hypot(s.sim_pose.x - r[0], s.sim_pose.y - r[1])
        compared += 1
        if err > worst:
            worst, at = err, f.frame
    theirs = dict(events or {})
    return {"max_xy_error_m": worst, "at_frame": at, "frames_compared": compared,
            "events_replay": {str(k): v for k, v in sorted(mine.items())},
            "events_seats": {str(k): v for k, v in sorted(theirs.items())},
            "events_match": mine == theirs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="the seats run's directory")
    ap.add_argument("--map", required=True, help="the map directory it ran on")
    ap.add_argument("--project", default=".",
                    help="the project the run's scenario file is relative to (default: here)")
    ap.add_argument("--entity", default="walker")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    run = Path(args.run)
    here = Path(__file__).resolve()
    sys.path.insert(0, str(here.parents[2] / "scensim_launch" / "scripts"))
    import gap_trace
    from scensim.behaviour import seats
    result = json.loads((run / "result.json").read_text())
    traces = [gap_trace.load_trace(str(p))
              for p in sorted((run / "gap_trace").glob("*.jsonl"))]
    if len(traces) != 1:
        raise SystemExit(f"{run}: {len(traces)} truth files; one episode expected")
    trace = traces[0]
    scenario = result["scenario"]
    sfile = Path(scenario["file"])
    env = {"SCENSIM_SCENARIO": str(sfile if sfile.is_absolute()
                                   else Path(args.project).resolve() / sfile),
           "SCENSIM_PARAMETERS": json.dumps(scenario.get("parameters") or {}),
           "SCENSIM_RUN_DIR": str(run), "SCENSIM_RUN_SEED": str(scenario.get("seed") or 0),
           "SCENSIM_MAP_DIR": args.map, "SCENSIM_COMMANDS": json.dumps([args.entity])}
    if not Path(env["SCENSIM_SCENARIO"]).is_file():
        raise SystemExit(f"{env['SCENSIM_SCENARIO']}: the run's scenario is not there")
    models, ego = seats.build(env)
    from scensim_batch.compile import compile_scenario
    from scensim_batch.map_export import export
    from scensim_batch.world_lanelet import LaneletWorld
    doc = export(args.map)
    world = LaneletWorld(doc["lanelets"], doc["map"], doc["map_sha256"])
    c = compile_scenario(env["SCENSIM_SCENARIO"], [seats.record_of(env)], world)
    i = [e.name for e in c.entities].index(args.entity)
    events = {}
    dec = run / "attachments"
    for p in dec.glob(f"*/{seats.DECISIONS}"):
        for line in p.read_text().splitlines():
            d = json.loads(line)
            if d.get("entity") == args.entity:
                events[int(d["frame"])] = d["event"]
    out = replay(trace, models[args.entity], args.entity, ego, float(c.x[0, i]),
                 float(c.y[0, i]), trace.episode.step_time or 0.05, events)
    out.update(run=str(run), entity=args.entity, ego=ego)
    text = json.dumps(out, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
