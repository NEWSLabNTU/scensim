#!/usr/bin/env bash
# 094 P2's runs, ours: the MuSHR drift task on K2's environment through WheeledLab's own
# train_rl.py under 241's harness (wheeledlab_bench at the fork's pin), as stock's run_p1.sh runs
# stock's: the same stages, sizes, iterations, timers and warm-up.
#
#   run_p2.sh <stage: smoke|seeds|seed|sweep> <out dir> [row: b|a] [starts: stock|uniform]
#   (seed: the one seed SEED names, into the seeds stage's directory)
#
# Host settings (environment): FORK, the WheeledLab checkout at the harness pin (isaaclab-3.0
# 5de128c or later: --task-package); OV, the Isaac Lab
# python; GPU (default 0); SHARED=1 runs on a shared GPU (--allow-shared: its wall-clock is marked
# contended and stays out of the comparison; samples-to-pass does not depend on load).
set -euo pipefail
stage=${1:?stage: smoke|seeds|sweep}; out=${2:?out dir}; row=${3:-b}; starts=${4:-stock}
FORK=${FORK:?FORK: the WheeledLab checkout}; OV=${OV:?OV: the Isaac Lab overlay python}
GPU=${GPU:-0}
here=$(cd "$(dirname "$0")" && pwd)          # scensim_batch/scripts
repo=$(cd "$here/../../.." && pwd)
out=$(realpath -m "$out")
case $row in b) comp=() ;; a) comp=(env.drift_component=roboracer_vesc.component:RoboRacerVesc) ;; *) echo "row: a|b" >&2; exit 2 ;; esac
export OMNI_KIT_ACCEPT_EULA=YES PYTHONNOUSERSITE=1 CUDA_VISIBLE_DEVICES=$GPU WHEELEDLAB_ENABLE_CAMERAS=0
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-/usr/share/vulkan/icd.d/nvidia_icd.json}
export SCENSIM_ASSET_ROOT=$FORK/source
export PYTHONPATH=$FORK/source/wheeledlab:$FORK/source/wheeledlab_tasks:$FORK/source/wheeledlab_rl:$FORK/source/wheeledlab_assets:$FORK/bench:$repo/src/sim_vehicle_ecu:$repo/src/sim_vehicle_spec:$repo/src/scensim_sampler:$repo/src/scensim_batch:$repo/scenarios/projects/roboracer/component/roboracer_vesc
gate=(--require-idle); [ "${SHARED:-0}" = 1 ] && gate=(--allow-shared)
hooks=(--sample-hook scensim_batch.start_pool:StartPool.refill --sample-hook scensim_batch.start_pool:StartPool.take)
# the harness records its commit and the task package's (wheeledlab_bench >= 5de128c), and
# refuses either dirty unless --allow-dirty (ALLOW_DIRTY=1, recorded)
prov=(--task-package scensim_batch); [ "${ALLOW_DIRTY:-0}" = 1 ] && prov+=(--allow-dirty)
mkdir -p "$out/$stage" "$out/seeds"
cd "$FORK"

# <name> <timers> <seed> <n_envs> <iters> <warmup>
run() {
    local name=$1 timers=$2 seed=$3 n=$4 iters=$5 warmup=$6
    local d="$out/${out_stage:-$stage}/$name"
    if [ -f "$d/summary.json" ] && grep -q '"closed": true' "$d/summary.json"; then
        echo "$name: done already"; return 0
    fi
    echo "$name: row=$row starts=$starts timers=$timers seed=$seed envs=$n iterations=$iters ($(date -Is))"
    env -u DISPLAY "$OV" -m wheeledlab_bench.launch --out "$d" --form "scensim-$row-$starts" \
        --timers "$timers" --warmup "$warmup" --seed "$seed" --gpu "$GPU" "${gate[@]}" "${hooks[@]}" "${prov[@]}" \
        -- "$here/train_drift.py" source/wheeledlab_rl/scripts/train_rl.py -r SCENSIM_DRIFT_CONFIG \
        train.log.no_wandb=True train.log.video=False agent.seed="$seed" \
        train.num_iterations="$iters" env_setup.num_envs="$n" env.starts="$starts" \
        env.starts_log="$d.starts.jsonl" "${comp[@]}" \
        train.log.run_name="p2-$row-$starts-${out_stage:-$stage}-$name" > "$d.log" 2>&1
}

case $stage in
smoke) run smoke sync 1 64 3 1 ;;
seeds) for s in 1 2 3 4 5; do run "seed$s" sync "$s" 1024 5000 20; done ;;
# one seed, so several run side by side (samples-to-pass does not depend on load): seed <n>
seed) s=${SEED:?SEED: the seed}; out_stage=seeds; run "seed$s" sync "$s" 1024 5000 20 ;;
sweep)
    for n in 256 1024 4096; do run "n$n" sync 1 "$n" 60 20; done
    run n1024-timers-off off 1 1024 60 20
    ;;
*) echo "unknown stage $stage" >&2; exit 2 ;;
esac
