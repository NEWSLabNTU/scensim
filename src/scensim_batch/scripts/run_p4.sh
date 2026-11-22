#!/usr/bin/env bash
# 094 P4's runs, ours: the lead-brake task (Scensim-LeadBrake-v0) through Isaac Lab's own
# train.py under 241's harness (wheeledlab_bench at the fork's pin), as stock's
# bench/p4_leadbrake/run_p4.sh runs P4-LeadBrake-v0: the same stages, sizes, iterations,
# timers, warm-up and evaluation schedule.
#
#   run_p4.sh <stage: smoke|seeds|seed|sweep> <out dir> [headway: stock|record]
#   (seed: the one seed SEED names, into the seeds stage's directory)
#
# stages (each writes under <out dir>/<stage>/):
#   smoke   3 iterations at 64 envs
#   seeds   5 seeds (1-5) at 1024 envs, 1500 iterations, a checkpoint every 50; then each
#           seed's checkpoints evaluated (eval_leadbrake.py, stock's bar) every 100 iterations up
#           to its first pass, and its last
#   sweep   throughput at N = 256, 1024, 4096 (60 iterations, 20 warm-up); timers off at 1024
#
# headway: the training headway (LeadBrakeEnvCfg.train_headway): stock, the comparable row's
# (stock's training distribution: an in-step reset's lead a policy step on), or record (every
# episode at its record's h). The evaluation is at h either way, as stock's.
#
# Host settings (environment), as run_p2.sh's: FORK (the WheeledLab checkout at the harness pin,
# isaaclab-3.0 b491b13 or later; its bench/p4_leadbrake holds stock's PPO settings), OV (the
# Isaac Lab python), ISAACLAB (its source checkout), GPU (default 0), SHARED=1, MAX_LOAD,
# WAIT_IDLE, CLEAN_ROWS and MAX_ROWS (the continuous gate), THREADS, ALLOW_DIRTY=1.
set -euo pipefail
stage=${1:?stage: smoke|seeds|seed|sweep}; out=${2:?out dir}; headway=${3:-stock}
FORK=${FORK:?FORK: the WheeledLab checkout}; OV=${OV:?OV: the Isaac Lab overlay python}
ISAACLAB=${ISAACLAB:?ISAACLAB: the Isaac Lab checkout, e.g. /var/tmp/aeon/isaaclab-3.0.0/src}
GPU=${GPU:-0}
case $headway in stock|record) ;; *) echo "headway: stock|record" >&2; exit 2 ;; esac
here=$(cd "$(dirname "$0")" && pwd)          # scensim_batch/scripts
repo=$(cd "$here/../../.." && pwd)
out=$(realpath -m "$out")
export OMNI_KIT_ACCEPT_EULA=YES PYTHONNOUSERSITE=1 CUDA_VISIBLE_DEVICES=$GPU
export VK_ICD_FILENAMES=${VK_ICD_FILENAMES:-/usr/share/vulkan/icd.d/nvidia_icd.json}
export PYTHONPATH=$FORK/bench:$FORK/bench/p4_leadbrake:$repo/src/sim_vehicle_ecu:$repo/src/sim_vehicle_spec:$repo/src/scensim_sampler:$repo/src/scensim_batch
gate=(--require-idle --max-load "${MAX_LOAD:-0.5}" --wait-idle "${WAIT_IDLE:-1800}")
[ "${SHARED:-0}" = 1 ] && gate=(--allow-shared)
if [ -n "${CLEAN_ROWS:-}" ] && [ "${SHARED:-0}" != 1 ]; then
    gate+=(--clean-rows "$CLEAN_ROWS" --max-rows "${MAX_ROWS:-$((4 * CLEAN_ROWS))}")
fi
# Kit's renderer on the run's GPU (index 0 under the mask), as run_p2.sh
kit=("--kit_args=--/renderer/multiGpu/activeCudaGpus=0,")
case $stage in seed|seeds) THREADS=${THREADS:-4} ;; esac
thr=()
if [ -n "${THREADS:-}" ]; then
    thr=("--threads=$THREADS")
    kit=("--kit_args=--/renderer/multiGpu/activeCudaGpus=0, --/plugins/carb.tasking.plugin/threadCount=$THREADS")
fi
hooks=(--sample-hook scensim_batch.start_pool:StartPool.refill --sample-hook scensim_batch.start_pool:StartPool.take)
prov=(--task-package scensim_batch); [ "${ALLOW_DIRTY:-0}" = 1 ] && prov+=(--allow-dirty)
mkdir -p "$out/$stage" "$out/seeds"

# <name> <timers> <seed> <n_envs> <iters> <warmup>; in its own directory (Isaac Lab writes logs/)
run() {
    local name=$1 timers=$2 seed=$3 n=$4 iters=$5 warmup=$6
    [ -n "${CLEAN_ROWS:-}" ] && [ "${SHARED:-0}" != 1 ] && \
        iters=$((warmup + ${MAX_ROWS:-$((4 * CLEAN_ROWS))} + 1))
    local d="$out/${out_stage:-$stage}/$name"
    if [ -f "$d/summary.json" ] && grep -q '"closed": true' "$d/summary.json"; then
        echo "$name: done already"; return 0
    fi
    mkdir -p "$d"
    echo "$name: headway=$headway timers=$timers seed=$seed envs=$n iterations=$iters ($(date -Is))"
    (cd "$d" && env -u DISPLAY "$OV" -m wheeledlab_bench.launch --out "$d" --form "scensim-b-$headway" \
        --timers "$timers" --warmup "$warmup" --seed "$seed" --gpu "$GPU" "${gate[@]}" "${hooks[@]}" "${prov[@]}" \
        -- "$here/train_leadbrake.py" "${thr[@]}" "$ISAACLAB/scripts/reinforcement_learning/train.py" \
        "${kit[@]}" --rl_library rsl_rl --task Scensim-LeadBrake-v0 --num_envs "$n" \
        --max_iterations "$iters" --seed "$seed" env.train_headway="$headway" \
        env.starts_log="$d.starts.jsonl" > "$d.log" 2>&1)
}

# evaluate one checkpoint: <name> <iteration>; prints the evaluator's JSON line
evaluate() {
    local name=$1 it=$2 ck d="$out/${out_stage:-$stage}"
    ck=$(ls "$d/$name"/logs/rsl_rl/p4_leadbrake/*/model_"$it".pt 2>/dev/null | head -1)
    [ -n "$ck" ] || { echo "{\"iteration\": $it, \"missing\": true}"; return 0; }
    env -u DISPLAY "$OV" "$here/eval_leadbrake.py" --checkpoint "$ck" "${kit[@]}" \
        --out "$d/$name.eval$it.json" > "$d/$name.eval$it.log" 2>&1
    grep '^{' "$d/$name.eval$it.log" | sed "s/^{/{\"iteration\": $it, /"
}

# a seed and its evaluations, stock's schedule
seed_run() {
    local s=$1
    run "seed$s" sync "$s" 1024 1500 20
    local evals="$out/seeds/seed$s.evals.jsonl" line
    [ -s "$evals" ] && { echo "seed$s: evaluated already"; return 0; }
    for it in $(seq 100 100 1400) 1499; do
        line=$(evaluate "seed$s" "$it"); echo "$line" >> "$evals"
        echo "seed$s it$it: $(echo "$line" | grep -oE '"success_rate": [0-9.]+')"
        if echo "$line" | grep -q '"pass": true' && [ "$it" != 1499 ]; then
            line=$(evaluate "seed$s" 1499); echo "$line" >> "$evals"; break
        fi
    done
}

case $stage in
smoke) run smoke sync 1 64 3 1 ;;
seeds) for s in 1 2 3 4 5; do seed_run "$s"; done ;;
seed) s=${SEED:?SEED: the seed}; out_stage=seeds; seed_run "$s" ;;
sweep)
    for n in 256 1024 4096; do run "n$n" sync 1 "$n" 60 20; done
    run n1024-timers-off off 1 1024 60 20
    ;;
*) echo "unknown stage $stage" >&2; exit 2 ;;
esac
