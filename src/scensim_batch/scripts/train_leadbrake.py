"""094 P4: Isaac Lab's own train.py on scensim's lead-brake task, as stock's run_p4.sh trains
P4-LeadBrake-v0 with it. It registers Scensim-LeadBrake-v0 (scensim_batch.tasks), whose PPO
settings are stock's (p4_leadbrake.agent, verbatim), then runs the script:

    python -m wheeledlab_bench.launch ... -- <this> <Isaac Lab>/scripts/reinforcement_learning/train.py \\
        --rl_library rsl_rl --task Scensim-LeadBrake-v0 --num_envs 1024 --max_iterations 1500 \\
        --seed 1 env.train_headway=stock env.starts_log=<jsonl>

The project settings are the env's hydra arguments: env.train_headway=record|stock,
env.starts_log=<jsonl>, env.pool_seed=<n>.

`--threads=N` (taken out before the script sees its arguments) caps the process's CPU threads:
OMP (torch's intra-op threads too), MKL, OpenBLAS and USD's, as train_drift.py's; torch is not
imported here, before Kit's app."""
import os
import runpy
import sys
from pathlib import Path

THREADS = None
for _a in list(sys.argv[1:]):
    if _a.startswith("--threads="):
        THREADS = int(_a.split("=", 1)[1])
        sys.argv.remove(_a)
if THREADS:
    for _k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
               "PXR_WORK_THREAD_LIMIT"):
        os.environ[_k] = str(THREADS)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
__import__("scensim_batch.tasks")      # registers Scensim-LeadBrake-v0
if os.environ.get("PPO_LOG"):          # per-update KL, clip fraction, learning rate (094 P4)
    from scensim_batch import ppo_log  # noqa: E402 (stdlib only until a PPO is built)
    ppo_log.install(os.environ["PPO_LOG"])

script, sys.argv = sys.argv[1], sys.argv[1:]
runpy.run_path(script, run_name="__main__")
