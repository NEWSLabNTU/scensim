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

Step 3 times them. The world server stamps `CLOCK_MONOTONIC` just before its tick call and when
it returns (the truth's `tick_mono_ns`, `tick_return_mono_ns`), on the clock acb's `mono_ns` reads
when both run under one boot (the truth's `world_boot_id` and the trace's `# boot_id` line must
match; otherwise the comparison is refused). For a frame with stamps, against the expected
send's `mono_ns`:

- `late` stays `late` when the send left before the tick-start stamp: truly late, the control
  left first and still reached CARLA after the tick began;
- `late` becomes `after_tick` when it left at or after the stamp: the tick was already under way
  when acb sent, which acb's view of the frames did not show;
- an `in_time` frame whose send left after the stamp is counted as `in_time_after_stamp`: the
  server began the tick after the send, within the RPC's send latency, which the stamp cannot
  see. The window from the stamp to the server's start is bounded by the tick call's duration
  (return minus start), whose distribution is reported beside the labels.

Controls match by value: throttle, brake and steer within FLOAT_TOL (CARLA keeps them as float32,
whose step near 1.0 is 6e-8; acb prints the float32 in full), the flags exactly. Not the gear:
under the automatic transmission (`manual_gear_shift` false, as acb sends) CARLA's read-back
holds the gear the car is in (1 while driving forward), not the 0 that was sent (seen on issue
135 step 2's run, 2026-11-24).
"""
import argparse
import csv
import json
import math
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
            and all(a[k] == b[k] for k in ("hand_brake", "reverse")))


def _sends(rows):
    """(applies in send order, clean: frame -> index of its expected send, raced: frame -> n)."""
    applies = [r for r in rows if r["kind"] == "apply"]
    for r in applies:
        r["f_obs"] = int(r["f_obs"])
        r["f_after"] = int(r["f_after"]) if r["f_after"] not in ("", None) else None
        r["control"] = control_of_row(r)
        r["mono_ns"] = int(r["mono_ns"])
    applies.sort(key=lambda r: (r["mono_ns"], r["i"]))
    clean, raced = {}, {}
    for n, r in enumerate(applies):
        if r["f_after"] is None:
            continue
        if r["f_after"] == r["f_obs"]:
            clean[r["f_obs"] + 1] = n         # the last one wins: applies are in send order
        elif r["f_after"] > r["f_obs"]:
            raced[r["f_obs"] + 1] = raced.get(r["f_obs"] + 1, 0) + 1
    return applies, clean, raced


def classify(rows, drops, truth):
    """`truth`: [(sim_frame, control dict)] in frame order. Returns (per-frame labels, counts)."""
    applies, clean, raced = _sends(rows)
    ticks = {int(r["f_obs"]): r["i"] for r in rows if r["kind"] == "tick"}
    # a drop between the tick rows of s - 1 and s leaves s unclassified
    dropped_at = [i for i, _ in drops]

    def touched(s):
        lo, hi = ticks.get(s - 1), ticks.get(s)
        if lo is None or hi is None:
            return bool(dropped_at)          # not bracketed: unknown if any row was dropped
        return any(lo < i < hi for i in dropped_at)

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


def timed(rows, labels, ticks):
    """Step 3: split `labels` by the world server's tick stamps, `ticks`: {sim_frame: (start_ns,
    return_ns)}. Returns (labels, offsets): offsets[label] lists, per frame, the expected send's
    `mono_ns` minus the tick's start, ns (`late`, `after_tick`, `in_time_after_stamp`)."""
    applies, clean, _ = _sends(rows)
    out, offsets = dict(labels), {"late": [], "after_tick": [], "in_time_after_stamp": []}
    for s, label in labels.items():
        if s not in ticks or s not in clean or label not in ("late", "in_time"):
            continue
        d = applies[clean[s]]["mono_ns"] - ticks[s][0]
        if label == "late":
            out[s] = "late" if d < 0 else "after_tick"
            offsets[out[s]].append(d)
        elif d >= 0:
            offsets["in_time_after_stamp"].append(d)
    return out, offsets


def _rank(v, p):
    return v[min(len(v) - 1, max(0, math.ceil(p * len(v)) - 1))]


def tick_windows(ticks):
    """The tick call's duration (return minus start) over the stamped frames, us."""
    d = sorted(r - st for st, r in ticks.values() if (st, r) != (0, 0))
    if not d:
        return {"n": 0}
    return {"n": len(d)} | {f"{k}_us": _rank(d, p) / 1e3 for k, p in
                            (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("p99", 0.99))} | {
        "max_us": d[-1] / 1e3}


def trace_boot_id(lines):
    """The `# boot_id <id>` line acb writes before its header, or None."""
    for line in lines:
        if line.startswith("# boot_id "):
            return line[len("# boot_id "):].strip() or None
    return None


def check_same_boot(trace_boot, world_boot):
    """CLOCK_MONOTONIC compares only under one boot: refuse otherwise, naming both."""
    if trace_boot is None or world_boot is None or trace_boot != world_boot:
        raise SystemExit(f"apply trace boot_id {trace_boot!r} and the world server's boot_id "
                         f"{world_boot!r} differ or are unknown: CLOCK_MONOTONIC times compare "
                         "only under one boot of one host; not timing them")


def truth_of(run, entity):
    """([(sim_frame, control)], {sim_frame: (tick start, tick return)}, world_boot_id)."""
    traces = sorted(Path(run).glob("gap_trace/*.jsonl"))
    if len(traces) != 1:
        raise SystemExit(f"{run}: {len(traces)} truth files; one episode expected")
    t = gap_trace.load_trace(str(traces[0]), require_end=False)
    out, ticks = [], {}
    for f in t.frames:
        if f.sim_frame is None:
            continue
        if f.tick_mono_ns is not None and f.tick_return_mono_ns is not None:
            ticks[f.sim_frame] = (f.tick_mono_ns, f.tick_return_mono_ns)
        s = f.entities.get(entity)
        if s is not None and s.control is not None:
            out.append((f.sim_frame, control_of_state(s.control)))
    return out, ticks, t.episode.world_boot_id


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", required=True, help="acb's apply trace (CSV)")
    ap.add_argument("--run", required=True, help="the run's directory (its gap_trace/)")
    ap.add_argument("--entity", default="ego")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    text = Path(a.trace).read_text().splitlines()
    rows, drops = read_trace(text)
    truth, ticks, world_boot = truth_of(a.run, a.entity)
    labels, counts = classify(rows, drops, truth)
    judged = counts.get("in_time", 0) + counts.get("late", 0) + counts.get("other", 0)
    out = {"run": str(a.run), "trace": str(a.trace), "entity": a.entity,
           "frames_with_control": len(truth), "judged": judged, "counts": counts,
           "late_frames": sorted(s for s, v in labels.items() if v == "late"),
           "other_frames": sorted(s for s, v in labels.items() if v == "other")[:50],
           "float_tol": FLOAT_TOL}
    if ticks:
        check_same_boot(trace_boot_id(text), world_boot)
        tlabels, offsets = timed(rows, labels, ticks)
        tcounts = {}
        for v in tlabels.values():
            tcounts[v] = tcounts.get(v, 0) + 1
        w = tick_windows(ticks)
        p95_ns = w.get("p95_us", 0.0) * 1e3
        out["timed"] = {
            "boot_id": world_boot, "stamped_frames": len(ticks), "counts": tcounts,
            "tick_call": w,
            "late_frames": sorted(s for s, v in tlabels.items() if v == "late"),
            "after_tick_frames": sorted(s for s, v in tlabels.items() if v == "after_tick"),
            "offset_us": {k: sorted(d / 1e3 for d in v) for k, v in offsets.items()},
            "after_tick_within_p95": sum(d <= p95_ns for d in offsets["after_tick"]),
            "in_time_after_stamp_within_p95":
                sum(d <= p95_ns for d in offsets["in_time_after_stamp"])}
    else:
        out["timed"] = None   # the world server did not stamp its ticks
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
