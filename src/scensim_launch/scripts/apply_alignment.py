#!/usr/bin/env python3
"""Issue 135, step 2: did acb's control for tick k reach CARLA before tick k?

    python3 apply_alignment.py --trace <acb apply trace.csv> --run <run dir> [--entity ego] \
        [--out f.json]

acb's apply trace (acb_bridge `apply_trace_path`, its apply_trace.rs) has one row per actuation
with the newest frame acb had taken (`f_obs`) and the newest its client had received when the
call returned (`f_after`), and the control as sent. The run's truth has, per frame, the control
CARLA held for the ego in the tick that ended at the frame's `sim_frame` (`control`; checked to
be that tick's, issue 135 step 1).

Per truth frame with the entity's `control`, CARLA frame s:

- `sent`: the `apply` rows with `f_obs == f_after == s - 1` (sent while acb's newest frame was
  still s - 1, by its own view before and after the call); the expected control is the last of
  them in send order;
- `raced`: an `apply` with `f_obs == s - 1` and `f_after >= s`: a tick finished during the
  call. Counted, not judged;
- `in_time`: the truth holds the expected control;
- `late`: it holds instead the control of the `apply` sent just before the expected one (in send
  order, any frame): the expected one reached CARLA after tick s began. A candidate, bounded by
  the stream delay: acb's view "still s - 1" is not "the server had not begun tick s";
- `ambiguous`: the expected control equals the one before it, so the two cannot be told apart;
- `other`: neither;
- `no_send`: no clean `apply` for s;
- `unclassified`: the writer dropped rows (`[acb_bridge log] N line(s) dropped`) between the
  frame's neighbouring `tick` rows: what acb sent there is not known.

Controls match by value: throttle, brake and steer within FLOAT_TOL (CARLA keeps them as float32,
whose step near 1.0 is 6e-8; acb prints the float32 in full), the flags and the gear exactly.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

FLOAT_TOL = 1e-6
FLOATS = ("throttle", "brake", "steer")
DROP = "[acb_bridge log]"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gap_trace  # noqa: E402


def read_trace(lines):
    """(rows, drops): rows as dicts in file order with `i` their position; drops as
    [(position, count)]."""
    rows, drops, header = [], [], None
    for i, line in enumerate(lines):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        if line.startswith(DROP):
            words = line[len(DROP):].split()
            drops.append((i, int(words[0]) if words and words[0].isdigit() else 1))
            continue
        cells = next(csv.reader([line]))
        if header is None:
            header = cells
            continue
        r = dict(zip(header, cells))
        r["i"] = i
        rows.append(r)
    return rows, drops


def control_of_row(r):
    return {"throttle": float(r["throttle"]), "brake": float(r["brake"]),
            "steer": float(r["steer"]), "hand_brake": r["hand_brake"] == "1",
            "reverse": r["reverse"] == "1", "gear": int(r["gear"])}


def control_of_state(c):
    return {"throttle": c.throttle, "brake": c.brake, "steer": c.steer,
            "hand_brake": c.hand_brake, "reverse": c.reverse, "gear": c.gear}


def same(a, b):
    return (all(abs(a[k] - b[k]) <= FLOAT_TOL for k in FLOATS)
            and all(a[k] == b[k] for k in ("hand_brake", "reverse", "gear")))


def classify(rows, drops, truth):
    """`truth`: [(sim_frame, control dict)] in frame order. Returns (per-frame labels, counts)."""
    applies = [r for r in rows if r["kind"] == "apply"]
    for r in applies:
        r["f_obs"], r["f_after"] = int(r["f_obs"]), (int(r["f_after"]) if r["f_after"] else None)
        r["control"] = control_of_row(r)
        r["mono_ns"] = int(r["mono_ns"])
    applies.sort(key=lambda r: (r["mono_ns"], r["i"]))
    ticks = {int(r["f_obs"]): r["i"] for r in rows if r["kind"] == "tick"}
    # a drop between the tick rows of s - 1 and s leaves s unclassified
    dropped_at = [i for i, _ in drops]

    def touched(s):
        lo, hi = ticks.get(s - 1), ticks.get(s)
        if lo is None or hi is None:
            return bool(dropped_at)          # not bracketed: unknown if any row was dropped
        return any(lo < i < hi for i in dropped_at)

    clean = {}
    raced = {}
    for n, r in enumerate(applies):
        if r["f_after"] is None:
            continue
        if r["f_after"] == r["f_obs"]:
            clean[r["f_obs"] + 1] = n         # the last one wins: applies are in send order
        elif r["f_after"] > r["f_obs"]:
            raced[r["f_obs"] + 1] = raced.get(r["f_obs"] + 1, 0) + 1
    labels, counts = {}, {}
    for s, held in truth:
        if touched(s):
            label = "unclassified"
        elif s not in clean:
            label = "no_send"
        else:
            n = clean[s]
            expected = applies[n]["control"]
            before = applies[n - 1]["control"] if n > 0 else None
            if before is not None and same(expected, before):
                label = "ambiguous"
            elif same(held, expected):
                label = "in_time"
            elif before is not None and same(held, before):
                label = "late"
            else:
                label = "other"
        labels[s] = label
        counts[label] = counts.get(label, 0) + 1
    counts["raced"] = sum(raced.get(s, 0) > 0 for s, _ in truth)
    counts["dropped_rows"] = sum(c for _, c in drops)
    counts["velocity_rows"] = sum(r["kind"] == "velocity" for r in rows)
    return labels, counts


def truth_controls(run, entity):
    traces = sorted(Path(run).glob("gap_trace/*.jsonl"))
    if len(traces) != 1:
        raise SystemExit(f"{run}: {len(traces)} truth files; one episode expected")
    t = gap_trace.load_trace(str(traces[0]), require_end=False)
    out = []
    for f in t.frames:
        s = f.entities.get(entity)
        if s is not None and s.control is not None and f.sim_frame is not None:
            out.append((f.sim_frame, control_of_state(s.control)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", required=True, help="acb's apply trace (CSV)")
    ap.add_argument("--run", required=True, help="the run's directory (its gap_trace/)")
    ap.add_argument("--entity", default="ego")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    rows, drops = read_trace(Path(a.trace).read_text().splitlines())
    truth = truth_controls(a.run, a.entity)
    labels, counts = classify(rows, drops, truth)
    judged = counts.get("in_time", 0) + counts.get("late", 0) + counts.get("other", 0)
    out = {"run": str(a.run), "trace": str(a.trace), "entity": a.entity,
           "frames_with_control": len(truth), "judged": judged, "counts": counts,
           "late_frames": sorted(s for s, v in labels.items() if v == "late"),
           "other_frames": sorted(s for s, v in labels.items() if v == "other")[:50],
           "float_tol": FLOAT_TOL}
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
