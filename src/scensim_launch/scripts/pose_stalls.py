#!/usr/bin/env python3
"""A body whose world pose lags its tick by a frame (issue 127), found in a gap trace.

    python3 pose_stalls.py <run dir | trace.jsonl> ... [--ego ego] [--out f.json]

A stall-then-double-step of entity e at frame k (issue 127's detector, written before its runs):
the world's step (`sim_pose`, in x and y) from k-1 to k is under STALL_M while SSv2's step
(`ssv2`) there is over MOVING_M, and the world's step from k to k+1 is between DOUBLE_LO and
DOUBLE_HI times SSv2's step from k to k+1. Frames k-1, k and k+1 must be consecutive and carry
the entity's world pose, and none of them its spawn frame.

The tracking error of a frame is the distance in x and y from `sim_pose` to `ssv2`: for a
kinematic body it is the pose it was not given; for a tracked one, how far physics is from SSv2.
Prints one JSON object: per run its entity-frames, its stalls (entity, frame and the steps) and
the tracking error's p50, p95 and max, then the totals.
"""
import argparse
import json
import math
import sys
from pathlib import Path

STALL_M = 0.001
MOVING_M = 0.05
DOUBLE_LO = 1.5
DOUBLE_HI = 2.5

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_trace  # noqa: E402


def _xy(p):
    return (p.x, p.y)


def _step(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def series(trace, skip=()):
    """{entity: [(frame, world (x, y) or None, ssv2 (x, y), spawn)]} in frame order."""
    out = {}
    for f in trace.frames:
        for name, s in f.entities.items():
            if name in skip:
                continue
            out.setdefault(name, []).append(
                (f.frame, None if s.sim_pose is None else _xy(s.sim_pose), _xy(s.ssv2), s.spawn))
    return out


def stalls(trace, skip=()):
    """Every stall-then-double-step (module doc) as a dict: entity, frame and the four steps."""
    found = []
    for name, rows in series(trace, skip).items():
        for (f0, w0, s0, sp0), (f1, w1, s1, sp1), (f2, w2, s2, sp2) in zip(rows, rows[1:],
                                                                           rows[2:]):
            if f1 != f0 + 1 or f2 != f1 + 1 or None in (w0, w1, w2) or sp0 or sp1 or sp2:
                continue
            ssv2_in, world_in = _step(s0, s1), _step(w0, w1)
            ssv2_out, world_out = _step(s1, s2), _step(w1, w2)
            if (world_in < STALL_M and ssv2_in > MOVING_M and ssv2_out > 0
                    and DOUBLE_LO * ssv2_out <= world_out <= DOUBLE_HI * ssv2_out):
                found.append({"entity": name, "frame": f1, "ssv2_step_in": ssv2_in,
                              "world_step_in": world_in, "ssv2_step_out": ssv2_out,
                              "world_step_out": world_out})
    return found


def _quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)] if q > 0 else xs[0]


def tracking(trace, skip=()):
    """The tracking error's p50, p95 and max (m) over the entity-frames with a world pose, and
    their count."""
    errs = [_step(w, s) for rows in series(trace, skip).values() for _, w, s, _ in rows
            if w is not None]
    return {"entity_frames": len(errs), "p50": _quantile(errs, 0.5),
            "p95": _quantile(errs, 0.95), "max": max(errs) if errs else None}


def traces_of(path):
    p = Path(path)
    return sorted(p.glob("gap_trace/*.jsonl")) if p.is_dir() else [p]


def report(paths, skip=("ego",)):
    runs, total, frames = [], 0, 0
    for path in paths:
        for tp in traces_of(path):
            t = gap_trace.load_trace(str(tp), require_end=False)
            st, tr = stalls(t, skip), tracking(t, skip)
            runs.append({"trace": str(tp), "npc_motion": t.episode.npc_motion,
                         "stalls": st, "tracking": tr})
            total += len(st)
            frames += tr["entity_frames"]
    return {"thresholds": {"stall_m": STALL_M, "moving_m": MOVING_M,
                           "double": [DOUBLE_LO, DOUBLE_HI]},
            "runs": runs, "stalls": total, "entity_frames": frames}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", help="run directories (their gap_trace/) or traces")
    ap.add_argument("--ego", action="append", default=None,
                    help="an entity left out (default: ego); repeatable")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    r = report(a.paths, tuple(a.ego or ("ego",)))
    text = json.dumps(r, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
