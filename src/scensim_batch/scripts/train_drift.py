"""094 P2: WheeledLab's own train_rl.py on scensim's drift task. It registers the gym task
Scensim-MushrDriftRL-v0 (scensim_batch.tasks) and a run config SCENSIM_DRIFT_CONFIG, which is
stock's RSS_DRIFT_CONFIG (WheeledLab's wheeledlab_rl.configs.runs) with only the task name ours,
then runs the script as stock's run does:

    python -m wheeledlab_bench.launch ... -- <this> <WheeledLab>/source/wheeledlab_rl/scripts/train_rl.py \\
        -r SCENSIM_DRIFT_CONFIG train.log.no_wandb=True ...

SCENSIM_ASSET_ROOT (a host setting) names WheeledLab's source/ (the MuSHR's asset). The project
settings are arguments: env.starts=stock|uniform, env.starts_log=<jsonl>, env.pool_seed=<n>,
env.drift_component=<name> (row a; none: row b).

`--threads=N` (taken out before the script sees its arguments) caps the process's CPU threads:
OMP, MKL, OpenBLAS and USD's (PXR_WORK_THREAD_LIMIT) at N, and torch's intra-op threads once
torch loads, so several seeds on one shared host do not oversubscribe it (133, 2026-11-22: five
seeds of ~97 threads each ran ten times slower); the harness records it with the arguments."""
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
__import__("scensim_batch.tasks")      # registers Scensim-MushrDriftRL-v0


def _register_run_config():
    from wheeledlab_rl import configs
    from wheeledlab_rl.utils.hydra import register_run_to_hydra

    from scensim_batch.tasks.drift_run import SCENSIM_DRIFT_CONFIG
    configs.SCENSIM_DRIFT_CONFIG = SCENSIM_DRIFT_CONFIG    # rl_run_cfg_from_dict looks it up
    register_run_to_hydra("SCENSIM_DRIFT_CONFIG", SCENSIM_DRIFT_CONFIG)


def _startup_then_ours():
    """WheeledLab's startup (it launches Isaac's app, then imports its tasks and run configs),
    then ours: train_rl.py takes `startup` from that module after this patch."""
    import wheeledlab_rl.startup as su
    stock = su.startup

    def startup(*a, **k):
        out = stock(*a, **k)
        if THREADS:
            import torch
            torch.set_num_threads(THREADS)
            torch.set_num_interop_threads(THREADS)
        _register_run_config()
        return out
    su.startup = startup



def _idempotent_space_serialization():
    """WheeledLab's hydra flow (written for manager-based envs) serializes a config's spaces at
    registration, then updates a fresh copy (int spaces) from that serialized dict, which a
    DirectRLEnv's int spaces refuse. Our config holds them serialized
    (MushrDriftRLEnvCfg), so this makes serializing a serialized space a no-op; the flow
    deserializes them after, as for any env. Local to this run (stock's are manager-based)."""
    from isaaclab.envs.utils import spaces
    stock = spaces.serialize_space

    def serialize_space(space):
        return space if isinstance(space, str) else stock(space)
    spaces.serialize_space = serialize_space


_idempotent_space_serialization()
_startup_then_ours()
script, sys.argv = sys.argv[1], sys.argv[1:]
runpy.run_path(script, run_name="__main__")
