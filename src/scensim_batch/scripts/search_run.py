"""092 K11c's runner, INTERIM: one generation of a search (scensim-sample search) run in the
batch, on CPU, its outcomes written for `scensim-sample search next`.

    python search_run.py --records <dir>/g<t>.jsonl --scenario <xosc> --world <map export .json>
        --out <dir> [--steps 400] [--step-time 0.05] [--walker walker]

Every record is a slot of one BatchRun: the scenario compiled for the records, the ego a point
mass driven by `aeb_ttc` (scensim_batch.pointmass: neither engine A nor B, and an invented
pilot), each slot run to its end or `--steps` steps. The batch's truth is exported to
`<out>/truth/` (scensim_batch.truth) and scored by `scensim.truth.slot_outcomes`, the closest
gap the seats judge measures, into `<out>/outcomes.jsonl`. A summary goes to `<out>/run.json`
and stdout.

Interim: when K2's `scensim bench` lands, this runner calls into it or is retired (roadmap 092,
"K11c's spec, completed"). Run with the system Python, scensim_batch, sim_vehicle_ecu, scensim
and scensim_launch's scripts importable; no Isaac, no GPU.
"""
import argparse
import json
import sys
import time
from pathlib import Path


def run(records, scenario, world, out, steps=400, step_time=0.05, walker="walker"):
    from sim_vehicle_ecu import batch as ecu_batch
    from scensim import truth as T
    from scensim_batch import core
    from scensim_batch.compile import compile_scenario
    from scensim_batch.pointmass import Accel, AebTtc, PointMass
    from scensim_batch.truth import TruthRecorder

    t0 = time.time()
    c = compile_scenario(scenario, records, world)
    names = [e.name for e in c.entities]
    if walker not in names:
        raise SystemExit(f"{scenario}: no entity {walker!r} (entities: {', '.join(names)})")
    comp = ecu_batch.load_batch(Accel, {}, {}, list(range(c.n)))
    r = core.BatchRun(c, world, PointMass(c.n), comp, step_time=step_time)
    r.reset()
    pilot = AebTtc(r, names.index(walker))
    truth = TruthRecorder(r, step_time=step_time, start_unix=0.0)
    truth.begin(r.obs)
    k = 0
    for k in range(1, steps + 1):
        obs = r.step(pilot(r.obs), step_time)
        truth.record(obs)
        if all(o != "running" for o in r.outcome()):
            break
    out = Path(out)
    truth.write(out / "truth")
    rows = T.slot_outcomes(out / "truth")
    (out / "outcomes.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n"
                                                for x in rows))
    ends = r.outcome()
    summary = {"slots": c.n, "steps": k, "step_time": step_time,
               "ego": "point mass (scensim_batch.pointmass), aeb_ttc", "runner": "interim",
               "outcomes": {o: ends.count(o) for o in sorted(set(ends))},
               "failed": sum(1 for x in rows if x["outcome"].get("failed")),
               "errors": sum(1 for x in rows if x["outcome"].get("error")),
               "seconds": round(time.time() - t0, 1)}
    (out / "run.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--records", required=True, help="a generation's records (JSONL)")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--world", required=True, help="the map export (.json)")
    ap.add_argument("--out", required=True, help="a new directory")
    ap.add_argument("--steps", type=int, default=400, help="each slot's cap (default 400)")
    ap.add_argument("--step-time", type=float, default=0.05)
    ap.add_argument("--walker", default="walker", help="the entity aeb_ttc brakes for")
    a = ap.parse_args(argv)
    from scensim_batch.world_lanelet import LaneletWorld
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out}: not empty")
    out.mkdir(parents=True, exist_ok=True)
    recs = [json.loads(x) for x in Path(a.records).read_text().splitlines() if x.strip()]
    world = LaneletWorld.load(a.world)
    print(json.dumps(run(recs, a.scenario, world, out, a.steps, a.step_time, a.walker)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
