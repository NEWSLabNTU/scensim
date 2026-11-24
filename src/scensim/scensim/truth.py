"""The run's truth file for judges (roadmap 092 K4, docs/design/truth-stream.md).

Each run's truth is the bridge's gap trace in ``runs/<id>/gap_trace/``, one file per episode,
recorded by default. A judge reads it through this module::

    from scensim import truth
    for trace in truth.load(run_dir):          # gap_trace.Trace, schema 2's names for either schema
        for frame in trace.frames:
            ego = frame.entities["ego"].sim_pose

and ``truth.boxes(trace, frame)`` gives each entity's declared box where the simulator had it.

A reference judge, the ego's closest approach to any other entity, box to box::

    judges:
      - name: closest
        run: [python3, -m, scensim.truth, closest, --min-gap, "0.5"]

It measures between the scenario's declared boxes, placed at the simulator's poses (the body
pose with the entity's origin offset taken back off), so the gap is the clearance between the
boxes SSv2 judges collisions with, where the simulator put them. Its verdict is ``failed`` when
that gap goes below ``--min-gap`` (metres; negative is penetration), naming the entity, frame and
time. It prints one JSON object (scensim.judges).

``truth.clock(traces, mode, max_lag_s, rtf)`` is the run's clock record (time-and-ticking.md,
lockstep and paced): each frame's lag behind wall time, from the bridge's ``wall_ns``.
"""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

from scensim import episodes

_MODULES = {}


def _module(name: str):
    """A library module of scensim_launch's scripts (gap_trace, gap_geometry): installed, else
    this workspace's source tree."""
    if name in _MODULES:
        return _MODULES[name]
    from scensim import gap
    try:
        here = Path(gap.tool("gap_oracle")[1]).parent
    except FileNotFoundError:
        raise FileNotFoundError(f"{name}: scensim_launch is neither installed nor beside scensim")
    spec = importlib.util.spec_from_file_location(name, here / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    _MODULES[name] = mod
    return mod


def files(run_dir) -> list:
    """The run's truth files, one per episode, in order."""
    return sorted((Path(run_dir) / episodes.GAP_TRACE).glob("*.jsonl"))


def load(run_dir, require_end=False) -> list:
    """Every episode's trace of the run (a trace cut short reads, without its end line)."""
    gt = _module("gap_trace")
    return [gt.load_trace(f, require_end=require_end) for f in files(run_dir)]


def boxes(trace, frame) -> dict:
    """Each entity of `frame` the simulator had: its declared box (gap_geometry.OrientedBox)
    at the simulator's pose, the entity's origin offset taken back off."""
    gg = _module("gap_geometry")
    out = {}
    for name, s in frame.entities.items():
        h = trace.entities.get(name)
        if h is None or s.sim_pose is None:
            continue
        body = gg.Pose2D(s.sim_pose.x, s.sim_pose.y, s.sim_pose.yaw)
        o = h.origin_offset
        entity = gg.entity_pose_from_actor(body, o.x, o.y, o.yaw)
        out[name] = gg.ssv2_box(entity, h.declared.center, h.declared.dimensions)
    return out


def closest(traces) -> dict:
    """The ego's smallest box-to-box gap to any other entity over the traces: ``{gap, entity,
    frame, sim_time, episode}``, or None without an ego or another entity."""
    gg = _module("gap_geometry")
    best = None
    for t in traces:
        egos = [h.name for h in t.headers if h.kind == "ego"]
        if not egos:
            continue
        for f in t.frames:
            b = boxes(t, f)
            for ego in egos:
                if ego not in b:
                    continue
                for name, box in b.items():
                    if name == ego:
                        continue
                    d = gg.signed_distance(b[ego], box)
                    if best is None or d < best["gap"]:
                        best = {"gap": d, "ego": ego, "entity": name, "frame": f.frame,
                                "sim_time": f.sim_time, "episode": t.episode.episode}
    return best


def start_frames(trace):
    """S, the frames before SSv2's startNpcLogic (092 K2.4; batch-executor.md section 6,
    scenario time): the frame number of the first line whose ``npc_logic_started`` is true,
    less the first line's. None when it cannot be known: no line says (a trace written before
    the field), NPC logic never started, a line before it does not say, or a frame before it
    is missing (dropped: the count would be short; 243)."""
    frames = sorted(trace.frames, key=lambda f: f.frame)
    first = next((f for f in frames if f.npc_logic_started), None)
    if first is None:
        return None
    before = [f for f in frames if f.frame < first.frame]
    if any(f.npc_logic_started is None for f in before):
        return None
    numbers = [f.frame for f in before] + [first.frame]
    if numbers != list(range(numbers[0], first.frame + 1)):
        return None
    return first.frame - numbers[0]


CLOCK_MODES = ("lockstep", "paced")


def lags(trace, rtf=1.0) -> list:
    """Each frame's lag behind wall time, seconds, from the trace's first frame that has a wall
    stamp: ``(wall_k - wall_0) - (sim_k - sim_0) / rtf``, positive when the world is behind.
    Frames without ``wall_ns`` (a trace written before it existed) are skipped."""
    out, base = [], None
    for f in trace.frames:
        if f.wall_ns is None:
            continue
        sim = f.sim_time_ns if f.sim_time_ns is not None else round(f.sim_time * 1e9)
        if base is None:
            base = (f.wall_ns, sim)
        out.append(((f.wall_ns - base[0]) - (sim - base[1]) / rtf) / 1e9)
    return out


def settings(project_settings, ssv2=None) -> dict:
    """testbench.yaml's ``clock`` with its defaults: {mode, max_lag_s, rtf}. ``ssv2`` is the
    run's own SSv2 settings (testbench, suite, item and call merged, scensim.ssv2.merge), whose
    real-time factor is the one the run ran at; without it, the testbench's."""
    c = (project_settings or {}).get("clock") or {}
    if ssv2 is None:
        ssv2 = (project_settings or {}).get("ssv2") or {}
    return {"mode": c.get("mode", "lockstep"), "max_lag_s": c.get("max_lag_s"),
            "rtf": float(ssv2.get("global_real_time_factor", 1.0) or 1.0)}


def problems(project_settings) -> list:
    """testbench.yaml's ``clock``, checked: (where, message) pairs."""
    ps = project_settings or {}
    c = ps.get("clock")
    if c is None:
        return []
    if not isinstance(c, dict):
        return [("clock", "is {mode: lockstep|paced, max_lag_s: seconds}")]
    out = [(f"clock.{k}", "unknown key (mode, max_lag_s)") for k in c if k not in ("mode", "max_lag_s")]
    mode = c.get("mode", "lockstep")
    if mode not in CLOCK_MODES:
        out.append(("clock.mode", f"is lockstep or paced, not {mode!r}"))
    lag = c.get("max_lag_s")
    if lag is not None and not (isinstance(lag, (int, float)) and not isinstance(lag, bool)
                                and lag > 0 and math.isfinite(lag)):
        out.append(("clock.max_lag_s", "is a positive number of seconds"))
    if mode == "paced":
        if lag is None:
            out.append(("clock.max_lag_s", "a paced clock needs its budget, seconds of lag"))
        rtf = ((ps.get("ssv2") or {}).get("global_real_time_factor", 1.0))
        if rtf != 1 and rtf != 1.0:
            out.append(("clock.mode", f"paced holds simulated time to wall time, so "
                                      f"ssv2.global_real_time_factor must be 1, not {rtf}"))
        if ((ps.get("logging") or {}).get("gap_trace")) is False:
            out.append(("clock.mode", "paced measures its lag from the truth file: "
                                      "logging.gap_trace: false cannot be paced"))
    return out


def _rank(sorted_xs, q):
    return sorted_xs[min(len(sorted_xs) - 1, max(0, math.ceil(q * len(sorted_xs)) - 1))]


def clock(traces, mode="lockstep", max_lag_s=None, rtf=1.0) -> dict:
    """The result's ``clock``, or None when no frame has a wall stamp. ``ok`` is false only in
    paced mode, when a frame's lag exceeds ``max_lag_s``; a lockstep run's lag is a record."""
    xs = [x for t in traces for x in lags(t, rtf)]
    if not xs:
        return None
    srt = sorted(xs)
    over = sum(x > max_lag_s for x in xs) if max_lag_s is not None else 0
    out = {"mode": mode, "frames": len(xs),
           "lag_s": {"max": round(srt[-1], 6), "p50": round(_rank(srt, 0.5), 6),
                     "p99": round(_rank(srt, 0.99), 6), "final": round(xs[-1], 6)},
           "frames_over": over, "ok": not (mode == "paced" and over > 0)}
    if max_lag_s is not None:
        out["max_lag_s"] = max_lag_s
    if rtf != 1.0:
        out["global_real_time_factor"] = rtf
    return out


def commands(traces, lockstep=True) -> dict:
    """The result's ``commands`` (roadmap 092 K12, D7), or None when no entity is commanded.

    Per commanded entity (role ``model``): the frames it was moved by a command, its lag in
    frames (p50, p95, max) and the frames before its first command. ``cmd_frame`` is the world's
    frame the command answered (a truth frame's ``sim_frame``, as the gate's ``DONE``), so the
    lag is this frame's number minus that truth frame's; a ``cmd_frame`` no truth frame names is
    ``unmatched``. A frame before SSv2 starts NPC logic (``npc_logic_started`` false) and before
    the entity's first command is ``held``, not uncommanded: a model waits for it, as SSv2's own
    NPCs do (issue 163). From the
    world server's counts, the commands naming an unknown entity, the gate's misses, the
    dropped datagrams and the commands dropped as stale (each episode's last frame; ``stale``
    is a record, outside ``ok``: a leak to see, never a failure). Under lockstep ``ok`` holds when every frame
    after an entity's first has lag 1 (its first frame precedes any answer): else the run is an
    error run (``command_lag``). Free-running, the lag is a record and ``ok`` is true."""
    per, counts, seen = {}, {"unknown_entity": 0, "gate_misses": 0, "malformed": 0,
                             "stale": 0}, False
    for t in traces:
        models = [n for n, h in t.entities.items() if h.role == "model"]
        by_sim = {f.sim_frame: f.frame for f in t.frames if f.sim_frame is not None}
        last = None
        for f in t.frames:
            if f.commands is not None:
                last = f.commands
            for n in models:
                s = f.entities.get(n)
                if s is None or s.cmd_frame is None:
                    continue
                seen = True
                e = per.setdefault(n, {"lags": [], "uncommanded": 0, "unmatched": 0, "held": 0})
                if s.cmd_frame == 0:
                    if e["lags"]:
                        e["lags"].append(None)   # a command lost after the first: no answer
                    elif f.npc_logic_started is False:
                        e["held"] += 1           # SSv2's NPCs not started: no model runs (163)
                    else:
                        e["uncommanded"] += 1
                elif s.cmd_frame in by_sim:
                    e["lags"].append(f.frame - by_sim[s.cmd_frame])
                else:
                    e["unmatched"] += 1
        if last is not None:
            seen = True
            for k in counts:
                counts[k] += getattr(last, k)
    if not seen:
        return None
    out, ok = {"mode": "lockstep" if lockstep else "free", "entities": {}}, True
    for n, e in sorted(per.items()):
        lags = sorted(x for x in e["lags"] if x is not None)
        lost = sum(x is None for x in e["lags"])
        rec = {"commanded_frames": len(lags), "held_frames": e["held"],
               "uncommanded_frames": e["uncommanded"], "lost_frames": lost,
               "unmatched_frames": e["unmatched"]}
        if lags:
            rec["lag_frames"] = {"p50": _rank(lags, 0.5), "p95": _rank(lags, 0.95),
                                 "max": lags[-1]}
        if lockstep and (e["uncommanded"] > 1 or lost or e["unmatched"]
                         or any(x != 1 for x in lags)):
            ok = False
        out["entities"][n] = rec
    out.update(counts)
    out["ok"] = ok
    return out


def _closest(args) -> int:
    traces = load(args.run_dir)
    if not traces:
        print(json.dumps({"verdict": "error", "message": f"no truth file in {args.run_dir}/"
                          f"{episodes.GAP_TRACE}/ (logging.gap_trace: false?)"}))
        return 2
    c = closest(traces)
    if c is None:
        print(json.dumps({"verdict": "passed", "message": "no ego and other entity to measure",
                          "measure": "box to box"}))
        return 0
    gap = round(c["gap"], 3)
    failed = c["gap"] < args.min_gap
    print(json.dumps({
        "verdict": "failed" if failed else "passed",
        "message": (f"{c['ego']} came within {gap} m of {c['entity']} (frame {c['frame']}, "
                    f"{c['sim_time']:.2f} s), below {args.min_gap} m" if failed else
                    f"closest {gap} m, to {c['entity']} at {c['sim_time']:.2f} s"),
        "measure": "box to box: the declared boxes at the simulator's poses",
        "min_gap": args.min_gap, "closest": dict(c, gap=gap),
    }))
    return 1 if failed else 0


def slot_outcomes(batch_dir, threshold=0.0, margin_k=None) -> list:
    """092 K11b: the outcome of each batch slot's episode, as the search reads them, from the
    batch's truth export (scensim_batch.truth: `<dir>/slot_<k>_ep<e>/{truth.jsonl, sample.json,
    outcome.json}`). The score is closest() on the slot's truth, the same box-to-box gap the
    seats judge measures; a run fails when it is at most `threshold`. With `margin_k`, the score
    is sloped_score's (K11e), the failure still the gap at most `threshold`.
    `[{record, outcome}]`."""
    gt = _module("gap_trace")
    rows = []
    for d in sorted(Path(batch_dir).glob("slot_*_ep*"), key=_slot_key):
        rec = json.loads((d / "sample.json").read_text())
        rid = rec.get("id") if isinstance(rec, dict) else None
        if not rid:
            raise ValueError(f"{d}: sample.json has no record id")
        try:
            trace = gt.load_trace(d / "truth.jsonl", require_end=True)
        except (OSError, ValueError) as e:
            rows.append({"record": rid, "outcome": {"error": True, "message": str(e),
                                                    "run": d.name}})
            continue
        c = closest([trace])
        if c is None:
            rows.append({"record": rid, "outcome": {
                "error": True, "message": "no ego and other entity to measure", "run": d.name}})
            continue
        gap = float(c["gap"])
        out = {"score": gap}
        if margin_k is not None:
            out = sloped_score(d, margin_k)
        rows.append({"record": rid, "outcome": {
            **out, "failed": gap <= threshold, "contact": bool(trace.contacts),
            "error": False, "closest": {"entity": c["entity"], "frame": c["frame"],
                                        "sim_time": c["sim_time"]}, "run": d.name}})
    return rows


def sloped_score(slot_dir, k=1.0, draw="accept_u"):
    """092 K11e's score of one batch slot, from its saved files alone: the closest gap (the
    slot's truth.jsonl, closest()), and the walker's decision margin m = logit(u) - U, u the
    record's `draw` value (sample.json) and U the decision's (decision.json, the model's own
    record). score = gap where gap <= 0 (contact: a failure), else gap + k * max(m, 0): a
    walker that waited is ranked by how near it came to going, one that went (m < 0) by its
    gap. `{closest_gap, decision_margin, score}`; the margin None where the walker never
    decided (the score is then the gap)."""
    gt = _module("gap_trace")
    d = Path(slot_dir)
    c = closest([gt.load_trace(d / "truth.jsonl", require_end=True)])
    if c is None:
        raise ValueError(f"{d}: no ego and other entity to measure")
    gap = float(c["gap"])
    rec = json.loads((d / "sample.json").read_text())
    dec = json.loads((d / "decision.json").read_text())
    m = None
    if dec.get("decision") is not None:
        from scensim.behaviour.walker import GapAcceptanceWalker as W
        u = (rec.get("values") or {}).get(draw)
        if u is not None:
            threshold = W.draw(0, float(u))
        else:   # no draw searched: the walker's own, from the record's pilot seed
            seed = ((rec.get("seeds") or {}).get("pilots") or {}).get(dec.get("entity"))
            if seed is None:
                raise ValueError(f"{d}: the record has neither {draw!r} nor a pilot seed for "
                                 f"{dec.get('entity')!r}")
            threshold = W.draw(int(seed))
        if abs(threshold - float(dec["threshold_logit"])) > 1e-9:
            raise ValueError(f"{d}: the record's {draw} gives the threshold {threshold}, the "
                             f"model used {dec['threshold_logit']}")
        m = threshold - float(dec["decision"]["u"])
    score = gap if gap <= 0 or m is None else gap + k * max(m, 0.0)
    return {"closest_gap": gap, "decision_margin": m, "score": score}


def _slot_key(d):
    k, e = d.name[len("slot_"):].split("_ep")
    return int(k), int(e)


def _outcomes(args) -> int:
    rows = slot_outcomes(args.batch_dir, args.threshold)
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    if args.output == "-":
        sys.stdout.write(text)
    else:
        Path(args.output).write_text(text)
        n = sum(1 for r in rows if r["outcome"].get("failed"))
        e = sum(1 for r in rows if r["outcome"].get("error"))
        print(f"{len(rows)} slot episodes: {n} failed (score at most {args.threshold}), "
              f"{e} errors; {args.output}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m scensim.truth", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("closest", help="the ego's closest approach to any entity, box to box")
    c.add_argument("--min-gap", type=float, default=0.0,
                   help="fail below this gap, m (default 0: fail on contact)")
    c.add_argument("run_dir", type=Path)
    o = sub.add_parser("outcomes", help="092 K11b: each batch slot's closest gap as the "
                                        "search's outcomes (JSONL of {record, outcome})")
    o.add_argument("batch_dir", type=Path, help="the batch's truth export (slot_<k>_ep<e>/)")
    o.add_argument("--threshold", type=float, default=0.0,
                   help="a run fails at a score (gap, m) at most this (default 0)")
    o.add_argument("-o", "--output", default="-")
    args = ap.parse_args(argv)
    if args.cmd == "outcomes":
        if math.isnan(args.threshold):
            ap.error("--threshold: not a number")
        return _outcomes(args)
    if math.isnan(args.min_gap):
        ap.error("--min-gap: not a number")
    return _closest(args)


if __name__ == "__main__":
    sys.exit(main())
