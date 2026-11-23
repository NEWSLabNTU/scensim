#!/usr/bin/env python3
"""pose_error: the localization's horizontal error against the truth along the run (roadmap 086
C5d's NDT check).

Reads the run's recording (record/<entity>/, `logging.capture: full` with
/localization/kinematic_state in `logging.topics`) and the ego_trace attachment's `ego.csv`
(scensim_isaac_world.course.ego_trace: the ego's truth per frame, map frame, simulation time).
Each kinematic state is matched by its header stamp (simulation time) with the truth
interpolated there; samples from the first 10 s after the first state are left out (initial
alignment), as the nvtl judge leaves them. Passes when the 95th percentile of the horizontal
error is at most --max-p95 m; the maximum is reported beside it, not judged. No samples, no
recording or no trace is an error, not a pass.

    python3 judges/pose_error.py [--max-p95 0.2] <run dir>
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

STATE = "/localization/kinematic_state"
SETTLE_S = 10.0


def read_states(bag_dir: Path):
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    storage = "mcap" if any(bag_dir.glob("*.mcap")) else "sqlite3"
    reader.open(rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id=storage),
                rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if STATE not in types:
        return []
    reader.set_filter(rosbag2_py.StorageFilter(topics=[STATE]))
    cls = get_message(types[STATE])
    out = []
    while reader.has_next():
        _, data, _ = reader.read_next()
        m = deserialize_message(data, cls)
        st = m.header.stamp
        p = m.pose.pose.position
        out.append((st.sec + st.nanosec * 1e-9, p.x, p.y))
    return out


def read_truth(path: Path):
    t, x, y = [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            t.append(float(r["t"]))
            x.append(float(r["x"]))
            y.append(float(r["y"]))
    return t, x, y


def interp(ts, xs, t):
    """xs at t, linear between the samples either side; None outside them."""
    import bisect

    i = bisect.bisect_left(ts, t)
    if i == 0 or i >= len(ts):
        return None
    f = (t - ts[i - 1]) / (ts[i] - ts[i - 1])
    return xs[i - 1] + f * (xs[i] - xs[i - 1])


def pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(math.ceil(q * (len(s) - 1)))))]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-p95", type=float, default=0.2)
    ap.add_argument("run_dir")
    a = ap.parse_args()
    run = Path(a.run_dir)
    bags = sorted(p.parent for p in run.glob("record/*/metadata.yaml"))
    trace = run / "attachments" / "ego_trace" / "ego.csv"
    if not bags or not trace.exists():
        print(json.dumps({"message": "no recording (logging.capture: full) or no ego_trace "
                                     "attachment's ego.csv in the run"}))
        return 2
    states = sorted(s for b in bags for s in read_states(b))
    tt, tx, ty = read_truth(trace)
    if not states or len(tt) < 2:
        print(json.dumps({"message": f"no {STATE} in the recording, or no truth"}))
        return 2
    t0 = states[0][0]
    err = []
    for t, x, y in states:
        if t - t0 < SETTLE_S:
            continue
        gx, gy = interp(tt, tx, t), interp(tt, ty, t)
        if gx is None:
            continue
        err.append(math.hypot(x - gx, y - gy))
    if not err:
        print(json.dumps({"message": "no state within the truth's span after the first "
                                     f"{SETTLE_S:g} s"}))
        return 2
    p95 = pct(err, 0.95)
    ok = p95 <= a.max_p95
    print(json.dumps({"verdict": "passed" if ok else "failed", "bound_p95_m": a.max_p95,
                      "samples": len(err), "error_p95_m": round(p95, 4),
                      "error_median_m": round(pct(err, 0.5), 4),
                      "error_max_m": round(max(err), 4),
                      "message": f"horizontal error p95 {p95:.3f} m "
                                 f"{'<=' if ok else '>'} {a.max_p95} over {len(err)} samples"}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
