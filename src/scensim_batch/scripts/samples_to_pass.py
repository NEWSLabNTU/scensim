"""094's samples-to-pass, as 241 set it for both sides (P1, P2; 2026-11-22): eval_drift.py with
its defaults (32 envs, 30 s), one checkpoint a call, one process a call.

- coarse: every `coarse`-th saved checkpoint (250, 500, ... at a save interval of 50), in order,
  until the first that passes;
- back-fill: every saved checkpoint between the last coarse failure and that pass; the first
  that passes is the result, exact to the save interval;
- final: the last checkpoint, always;
- samples_to_pass = (first passing iteration + 1) x steps per env x envs (model_N is saved after
  iteration N's update, counting from 0); no pass: "no pass by N iterations", not a number.

Every evaluated checkpoint's line goes to <out>.jsonl (iteration, passed, share_clean,
slip_deg_median, speed_mean, phase), the result to <out>.json. A line already in the jsonl is
not evaluated again, so a rerun after the run has saved more checkpoints goes on.

    python samples_to_pass.py --run-path <run dir> --out <prefix> [--eval <eval_drift.py>]
        [--eval-arg=--row --eval-arg=a ...] [--envs-train 1024] [--steps-per-env 128]
        [--coarse 250] -- <python> [launcher args]

`--eval`: the evaluator (default scensim_batch's eval_drift.py; stock's P1 passes its
bench/p1/eval_drift.py, so both sides run this one search). Each call is
`<python> [launcher args] <eval> --headless --run-path <run> --checkpoint <N> --out <json>
[eval args]`; the evaluator writes a JSON with passed, share_clean, slip_deg_median,
speed_mean and laps_median, as both eval_drift.py do. `--eval-arg` (repeatable) goes to it
as given: ours takes --row and --starts, stock's --run-config. Everything after `--` is how to
run the evaluator (the Isaac Lab python and its environment are the caller's).
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def saved(run_path):
    return sorted(int(re.search(r"model_(\d+)\.pt$", m).group(1))
                  for m in glob.glob(os.path.join(run_path, "models", "model_*.pt")))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--" not in argv:
        raise SystemExit("give the python to run eval_drift.py after --")
    i = argv.index("--")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-path", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--eval", default=str(HERE / "eval_drift.py"))
    ap.add_argument("--eval-arg", action="append", default=[])
    ap.add_argument("--envs-train", type=int, default=1024)
    ap.add_argument("--steps-per-env", type=int, default=128)
    ap.add_argument("--coarse", type=int, default=250)
    a = ap.parse_args(argv[:i])
    runner = argv[i + 1:]
    lines = Path(a.out + ".jsonl")
    done = {}
    if lines.exists():
        for line in lines.read_text().splitlines():
            if line.strip():
                o = json.loads(line)
                done[o["iteration"]] = o

    def evaluate(it, phase):
        if it in done:
            return done[it]["passed"]
        js = f"{a.out}.ckpt{it}.json"
        cmd = runner + [a.eval, "--headless", "--run-path", a.run_path,
                        "--checkpoint", str(it), "--out", js] + a.eval_arg
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(js):
            tail = (r.stdout + r.stderr)[-2000:]
            raise SystemExit(f"eval of checkpoint {it} failed (rc {r.returncode}):\n{tail}")
        res = json.load(open(js))
        o = {"iteration": it, "phase": phase, "passed": res["passed"],
             "share_clean": res["share_clean"], "slip_deg_median": res["slip_deg_median"],
             "speed_mean": res["speed_mean"], "laps_median": res["laps_median"]}
        done[it] = o
        with open(lines, "a") as f:
            f.write(json.dumps(o) + "\n")
        print(json.dumps(o), flush=True)
        return o["passed"]

    its = saved(a.run_path)
    if not its:
        raise SystemExit(f"no checkpoints in {a.run_path}/models")
    coarse = [it for it in its if it > 0 and it % a.coarse == 0]
    first, last_fail = None, 0
    for it in coarse:
        if evaluate(it, "coarse"):
            first = it
            break
        last_fail = it
    if first is not None:
        for it in [x for x in its if last_fail < x < first]:
            if evaluate(it, "back-fill"):
                first = it
                break
    final = its[-1]
    final_passed = evaluate(final, "final")
    if first is None and final_passed:      # the last checkpoint passes past the last coarse one
        for it in [x for x in its if last_fail < x <= final]:
            if evaluate(it, "back-fill"):
                first = it
                break
    out = {"run_path": os.path.abspath(a.run_path), "eval": os.path.abspath(a.eval),
           "eval_args": a.eval_arg,
           "iterations_saved": final, "final_passed": final_passed,
           "first_pass_iteration": first,
           "samples_to_pass": None if first is None
           else (first + 1) * a.steps_per_env * a.envs_train,
           "result": (f"passed at iteration {first}" if first is not None
                      else f"no pass by {final} iterations")}
    Path(a.out + ".json").write_text(json.dumps(out, indent=1))
    print("SAMPLES_TO_PASS", json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
