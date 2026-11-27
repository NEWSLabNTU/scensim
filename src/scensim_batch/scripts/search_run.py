"""092 K11c's runner, INTERIM: one generation of a search (scensim-sample search) run in the
batch, on CPU, its outcomes written for `scensim-sample search next`.

    python search_run.py --records <dir>/g<t>.jsonl --scenario <xosc> --world <map export .json>
        --out <dir> [--steps 400] [--step-time 0.05] [--walker walker] [--truth]

Every record is a slot of one BatchRun: the scenario compiled for the records, the ego a point
mass driven by `aeb_ttc` (scensim_batch.pointmass: neither engine A nor B, and an invented
pilot), each slot run to its end or `--steps` steps. Each slot is scored while the batch
runs (scensim_batch.score, 092 K11f): the closest gap the seats judge measures, into
`<out>/outcomes.jsonl`. With `--truth` the batch's truth is also exported to `<out>/truth/`
(scensim_batch.truth) and scored from the files by `scensim.truth.slot_outcomes` (092 K11b), and
the two must agree (`compare_outcomes`), or the run stops naming where. A summary goes to
`<out>/run.json` and stdout.

Run it from a pinned copy (a detached worktree or a copy at one commit) that nobody edits
while the search runs: every generation is a new process and imports the tree as it is then
(133's rule, after K11c's run spanned two commits).

Interim: when K2's `scensim bench` lands, this runner calls into it or is retired (roadmap 092,
"K11c's spec, completed"). Run with the system Python, scensim_batch, sim_vehicle_ecu, scensim
and scensim_launch's scripts importable; no Isaac, no GPU.
"""
import argparse
import json
import sys
import time
from pathlib import Path


# 092 K11f: the most the batch's score may differ from the export's (m), every other field equal
BAR = 1e-9


def compare_outcomes(batch, export, bar=BAR):
    """Stop (SystemExit) unless the batch's rows and the export's agree: the same records in the
    same order, each score (and closest_gap, decision_margin) within `bar` m, failed, contact,
    error and the closest entity and frame identical, its sim_time within `bar` s. The message
    names the slot, the episode, both values and the bar."""
    if [r.get("record") for r in batch] != [r.get("record") for r in export]:
        raise SystemExit("092 K11f: the batch's rows and the export's name other records")
    for a, b in zip(batch, export):
        oa, ob = a["outcome"], b["outcome"]
        run = ob.get("run", "")
        try:
            k, e = run[len("slot_"):].split("_ep")
        except ValueError:
            k, e = "?", "?"
        where = f"092 K11f: the batch's score and the export's disagree at slot {k}, episode {e}"

        def stop(what, x, y, unit=""):
            raise SystemExit(f"{where} ({a.get('record')}): {what} {x!r} in the batch, {y!r} "
                             f"from the export" + (f", bar {bar!r} {unit}" if unit else ""))
        if set(oa) != set(ob):
            stop("fields", sorted(oa), sorted(ob))
        for key in ("score", "closest_gap", "decision_margin"):
            if key not in ob:
                continue
            x, y = oa[key], ob[key]
            if (x is None) != (y is None) or (x is not None and abs(x - y) > bar):
                stop(key, x, y, "m")
        for key in ("failed", "contact", "error", "run", "message"):
            if oa.get(key) != ob.get(key):
                stop(key, oa.get(key), ob.get(key))
        if "closest" in ob:
            ca, cb = oa["closest"], ob["closest"]
            for key in ("entity", "frame"):
                if ca[key] != cb[key]:
                    stop(f"closest {key}", ca[key], cb[key])
            if abs(ca["sim_time"] - cb["sim_time"]) > bar:
                stop("closest sim_time", ca["sim_time"], cb["sim_time"], "s")


def run(records, scenario, world, out, steps=400, step_time=0.05, walker="walker",
        margin_k=None, anchors=None, ttc_length=None, corridor=None, truth=False):
    from sim_vehicle_ecu import batch as ecu_batch
    from scensim import truth as T
    from scensim_batch import core
    from scensim_batch.compile import compile_scenario
    from scensim_batch.pointmass import Accel, AebTtc, PointMass
    from scensim_batch.score import ClosestGap
    from scensim_batch.truth import TruthRecorder

    t0 = time.time()
    c = compile_scenario(scenario, records, world)
    names = [e.name for e in c.entities]
    if walker not in names:
        raise SystemExit(f"{scenario}: no entity {walker!r} (entities: {', '.join(names)})")
    comp = ecu_batch.load_batch(Accel, {}, {}, list(range(c.n)))
    # anchors: the map's resolved anchors, a car-follower's lane (092 K13 step v)
    r = core.BatchRun(c, world, PointMass(c.n), comp, step_time=step_time, anchors=anchors)
    r.reset()
    pilot = AebTtc(r, names.index(walker))
    # outcome.json names the scenario as the records do (the search spec's written path), so a
    # run's files do not depend on where this checkout is
    paths = {(x.get("scenario") or {}).get("path") for x in records}
    label = paths.pop() if len(paths) == 1 and None not in paths else str(scenario)
    score = ClosestGap(r)
    score.begin(r.obs)
    rec = None
    if truth:
        rec = TruthRecorder(r, step_time=step_time, start_unix=0.0, scenario=label)
        rec.begin(r.obs)
    lane = None
    if ttc_length and corridor is not None:   # the target's lane anchor: its centreline
        ent = c.entities[names.index(walker)]
        name = ((ent.model or {}).get("params") or [{}])[0].get("lane")
        if name not in (anchors or {}):
            raise SystemExit(f"--corridor: {walker!r} holds no lane anchor of --anchors")
        lane = anchors[name]
    ttc = (Ttc(names.index("ego"), names.index(walker), ttc_length, c.n, corridor, lane)
           if ttc_length else None)
    if ttc:
        ttc.add(r.obs)
    k = 0
    for k in range(1, steps + 1):
        obs = r.step(pilot(r.obs), step_time)
        score.record(obs)
        if rec is not None:
            rec.record(obs)
        if ttc:
            ttc.add(obs)
        if all(o != "running" for o in r.outcome()):
            break
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # each slot's walker decision, the model's own record (092 K11e): what the sloped score
    # reads, in memory here, and beside the truth and the record in an export, so it is
    # recomputable from the saved files
    mrecs = r.models.records().get(walker)
    decisions = None
    if mrecs is not None and all("threshold_logit" in m for m in mrecs):   # the walker's
        decisions = [{"entity": walker, "threshold_logit": m["threshold_logit"],
                      "decision": m["decision"]} for m in mrecs]
    rows = score.rows()
    if margin_k is not None:
        if decisions is None:
            raise SystemExit(f"margin_k: {walker!r} keeps no decision records (the sloped "
                             "score is the gap-acceptance walker's)")
        for x in rows:
            o = x["outcome"]
            if o.get("error"):
                continue
            k_slot = int(o["run"][len("slot_"):].split("_ep")[0])
            sloped = T.slope(o["score"], c.records[k_slot], decisions[k_slot], margin_k,
                             where=o["run"])
            x["outcome"] = {**sloped, **{q: o[q] for q in o if q != "score"}}
    if rec is not None:
        rec.write(out / "truth")
        for k_slot, d in enumerate(decisions or []):
            (out / "truth" / f"slot_{k_slot}_ep0" / "decision.json").write_text(
                json.dumps(d, sort_keys=True) + "\n")
        compare_outcomes(rows, T.slot_outcomes(out / "truth", margin_k=margin_k))
    if ttc and corridor is not None:   # 092 K13 step v: off M's line is invalid, not judged
        for i, x in enumerate(rows):
            lat = ttc.max_lateral[i]
            x["outcome"]["max_lateral"] = lat
            if lat > corridor:
                x["outcome"].update(error=True, failed=False, invalid=(
                    f"the ego left {walker}'s line: max |lateral| {lat:.3f} m > {corridor} m"))
    (out / "outcomes.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n"
                                                for x in rows))
    ends = r.outcome()
    summary = {"slots": c.n, "steps": k, "step_time": step_time,
               "ego": "point mass (scensim_batch.pointmass), aeb_ttc", "runner": "interim",
               "score": ("closest gap" if margin_k is None else
                         f"sloped: closest gap + {margin_k} m per logit of decision margin"),
               "scored": "in the batch" + (", the export agreeing" if truth else ""),
               "outcomes": {o: ends.count(o) for o in sorted(set(ends))},
               "failed": sum(1 for x in rows if x["outcome"].get("failed")),
               "errors": sum(1 for x in rows if x["outcome"].get("error")),
               "seconds": round(time.time() - t0, 1)}
    if ttc:   # 092 K13 step v: a secondary output, not the failure
        mins = ttc.minimum()
        (out / "ttc.jsonl").write_text("".join(json.dumps({"slot": i, "min_ttc": v}) + "\n"
                                               for i, v in enumerate(mins)))
        summary["min_ttc_under_1s"] = sum(1 for v in mins if v is not None and v < 1.0)
        if corridor is not None:
            summary["invalid"] = sum(1 for x in rows if x["outcome"].get("invalid"))
            summary["failed"] = sum(1 for x in rows if x["outcome"].get("failed"))
            summary["errors"] = sum(1 for x in rows if x["outcome"].get("error"))
            valid = [x for x in rows if not x["outcome"].get("error")]
            if valid:   # 092 K13 step v: the smallest closest gap, a secondary output
                low = min(valid, key=lambda x: x["outcome"]["score"])
                summary["min_closest_gap"] = {"gap": low["outcome"]["score"],
                                              "record": low.get("record")}
            (out / "outcomes.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n"
                                                        for x in rows))
    (out / "run.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


class Ttc:
    """092 K13 step v's secondary output: each slot's minimum time to collision of the ego
    behind `target` on one lane, (centre distance - length) / closing speed while closing; the
    two boxes share their length and centre offset (the case's cars). None: never closing.
    With `corridor` (m) and `lane` (a resolved lane anchor), also each slot's largest |lateral|
    of the ego from the target's line, the difference of their signed offsets from the lane's
    centreline (the target's own heading swings a few degrees as it corrects toward the
    centreline, which across its heading at tens of metres reads as metres), and the TTC only
    while that is within the corridor (133's guard)."""

    def __init__(self, ego, target, length, n, corridor=None, lane=None):
        import numpy as np
        self.e, self.t, self.length = ego, target, float(length)
        self.corridor = corridor
        self.best = [None] * n
        self.max_lateral = [0.0] * n
        if lane is not None:
            x, y = np.asarray(lane["x"], float), np.asarray(lane["y"], float)
            keep = np.r_[True, np.hypot(np.diff(x), np.diff(y)) > 1e-9]
            self.ax, self.ay = x[keep][:-1], y[keep][:-1]
            self.dx, self.dy = np.diff(x[keep]), np.diff(y[keep])
            self.l2 = self.dx ** 2 + self.dy ** 2

    def offset(self, px, py):
        """Signed offsets [N] of points from the lane's centreline (left positive)."""
        import numpy as np
        px, py = np.asarray(px, float)[:, None], np.asarray(py, float)[:, None]
        tt = np.clip(((px - self.ax) * self.dx + (py - self.ay) * self.dy) / self.l2, 0.0, 1.0)
        qx, qy = self.ax + tt * self.dx, self.ay + tt * self.dy
        d = np.hypot(px - qx, py - qy)
        k = np.argmin(d, axis=1)
        r = np.arange(len(k))
        side = np.sign(self.dx[k] * (py[r, 0] - self.ay[k]) - self.dy[k] * (px[r, 0] - self.ax[k]))
        return side * d[r, k]

    def add(self, obs):
        import math
        x, y, v = obs["x"], obs["y"], obs["v"]
        lats = None
        if self.corridor is not None:
            col = lambda a, j: a[:, j].detach().cpu().numpy()   # noqa: E731
            lats = abs(self.offset(col(x, self.e), col(y, self.e))
                       - self.offset(col(x, self.t), col(y, self.t)))
        for i in range(len(self.best)):
            dx, dy = float(x[i, self.e] - x[i, self.t]), float(y[i, self.e] - y[i, self.t])
            lat = float(lats[i]) if lats is not None else 0.0
            self.max_lateral[i] = max(self.max_lateral[i], lat)
            if self.corridor is not None and lat > self.corridor:
                continue
            gap = math.hypot(dx, dy) - self.length
            closing = float(v[i, self.e] - v[i, self.t])
            if closing > 1e-9:
                tt = max(gap, 0.0) / closing
                if self.best[i] is None or tt < self.best[i]:
                    self.best[i] = tt

    def minimum(self):
        return list(self.best)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--records", required=True, help="a generation's records (JSONL)")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--world", required=True, help="the map export (.json)")
    ap.add_argument("--out", required=True, help="a new directory")
    ap.add_argument("--steps", type=int, default=400, help="each slot's cap (default 400)")
    ap.add_argument("--step-time", type=float, default=0.05)
    ap.add_argument("--walker", default="walker", help="the entity aeb_ttc brakes for")
    ap.add_argument("--margin-k", type=float, default=None,
                    help="092 K11e: score sloped on the waiting branch, k m per logit of the "
                         "walker's decision margin (default: the closest gap alone)")
    ap.add_argument("--anchors", help="the map's anchors.resolved.json (a car-follower's lane, "
                    "092 K13 step v)")
    ap.add_argument("--ttc-length", type=float, default=None,
                    help="092 K13 step v: write each slot's minimum time to collision of the ego "
                         "behind --walker (ttc.jsonl), the cars' length in m")
    ap.add_argument("--corridor", type=float, default=None,
                    help="092 K13 step v (with --ttc-length): a slot whose ego leaves --walker's "
                         "line by more than this many m is invalid, an error row, not judged")
    ap.add_argument("--truth", action="store_true",
                    help="092 K11f: also export the batch's truth to <out>/truth/ (for K3's "
                         "replays and audits) and stop unless its score agrees with the batch's")
    a = ap.parse_args(argv)
    from scensim_batch.world_lanelet import LaneletWorld
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out}: not empty")
    out.mkdir(parents=True, exist_ok=True)
    recs = [json.loads(x) for x in Path(a.records).read_text().splitlines() if x.strip()]
    world = LaneletWorld.load(a.world)
    anchors = json.loads(Path(a.anchors).read_text())["anchors"] if a.anchors else None
    print(json.dumps(run(recs, a.scenario, world, out, a.steps, a.step_time, a.walker,
                         a.margin_k, anchors, a.ttc_length, a.corridor, a.truth)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
