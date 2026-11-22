#!/usr/bin/env bash
# Roadmap 091 W23's regression: the synthetic stand-in for real logs, end to end, blind.
#
#     tools/w23_regression.sh OUT
#
# For each perturbation: p1 and p2 in protocol/perturbations (p1: representable by the fit's
# model; p2: with latency jitter it cannot hold, and a scan-matching reference), and p3, drawn
# blind (tools/draw_perturbation.py) into OUT/draw/p3, which nobody reads before the check:
# 1. The generator drives the perturbed twin through the protocol and writes the "real" logs as
#    the real car's rosbag2. The truth is sealed in OUT/sealed/<p>/, which the fit never reads.
# 2. The fit runs, its stages and then the twin in the loop, on the logs only. The loop fits the
#    tyres (W10): each axle's stiffness from M5's circles below 2 m/s^2, where the friction does
#    not bind, then each axle's friction from M6 and M6b, the stiffness held.
# 3. The harness runs: the unfitted and the fitted twins against the logs, by design note 5.3.
# 4. Only then does the recovery check read the sealed truth.
#
# Environment (host settings): ISAAC_ROOT, AIB (an autoware_isaac_bridge checkout, default this
# workspace's), VESC_MSGS_SETUP (a setup.bash with f1tenth's vesc_msgs), ROS_SETUP (default
# Humble's), WS_SETUP (this workspace's install/setup.bash). The ego config and rig are made in OUT
# from vehicles/roboracer.yaml. About 6 hours on one GPU host (118: 2026-11-21).
set -euo pipefail
OUT=${1:?usage: w23_regression.sh OUT}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
WS=$(cd "$ROOT/../../.." && pwd)
AIB=${AIB:-$WS/src/autoware_isaac_bridge}
ROS_SETUP=${ROS_SETUP:-/opt/ros/humble/setup.bash}
WS_SETUP=${WS_SETUP:-$WS/install/setup.bash}
: "${ISAAC_ROOT:?ISAAC_ROOT: where Isaac Sim is installed}" "${VESC_MSGS_SETUP:?VESC_MSGS_SETUP: a setup.bash with vesc_msgs}"
mkdir -p "$OUT/logs" "$OUT/sealed"
OUT=$(cd "$OUT" && pwd)
sys() {  # the system Python with ROS, this workspace and vesc_msgs
    env -i HOME="$HOME" PATH=/usr/bin:/bin bash -c "source $ROS_SETUP; source $WS_SETUP; source $VESC_MSGS_SETUP; $*"
}
isaac() {  # Isaac's Python with aib
    env -i HOME="$HOME" PATH=/usr/bin:/bin ISAAC_ROOT="$ISAAC_ROOT" bash -c \
        "source $AIB/src/aib/scripts/isaac_env.sh >/dev/null 2>&1; export PYTHONPATH=$AIB/src/aib:\$PYTHONPATH; cd $OUT; $*"
}
cp "$ROOT/vehicles/roboracer.yaml" "$OUT/roboracer.yaml"
printf 'rig: roboracer.rig.yaml\ndomain: 1\nnode_name: isaac_vehicle\nvehicle: {}\necu: {}\nsensors: {}\n' > "$OUT/ego.yaml"
sys "export PYTHONPATH=$AIB/src/aib:\$PYTHONPATH; cd $OUT; python3 -m aib.gen --spec roboracer.yaml -o roboracer.rig.yaml"
for pass in M5 M6,M6b; do  # refine_twin.py's --twin-cmd per pass: twin_eval_<pass>.sh FITTED RUNS
cat > "$OUT/twin_eval_${pass/,/_}.sh" <<EOF
#!/usr/bin/env bash
env -i HOME="\$HOME" PATH=/usr/bin:/bin ISAAC_ROOT="$ISAAC_ROOT" bash -c "source $AIB/src/aib/scripts/isaac_env.sh >/dev/null 2>&1; export PYTHONPATH=$AIB/src/aib:\\\$PYTHONPATH; cd $OUT; timeout -k 30 1800 python $HERE/twin_runs.py --ego ego.yaml --out \$2 --fitted \$1 --repetitions 1 --only $pass" > "\$2.log" 2>&1
EOF
chmod +x "$OUT/twin_eval_${pass/,/_}.sh"
done
# a step that finished leaves a marker in OUT/done/, and a rerun into the same OUT skips it (the
# logs' generation is most of the time); a step that did not finish is redone from the start
mkdir -p "$OUT/done"
if [ ! -e "$OUT/done/twin0" ]; then
    rm -rf "$OUT/logs/twin0"
    isaac "python $HERE/twin_runs.py --ego ego.yaml --out $OUT/logs/twin0 --repetitions 1" > "$OUT/twin0.log" 2>&1
    touch "$OUT/done/twin0"
fi
[ -e "$OUT/draw/p3/perturbation.yaml" ] || python3 "$HERE/draw_perturbation.py" --out "$OUT/draw/p3/perturbation.yaml"
seed=23
for p in p1 p2 p3; do
    src=$ROOT/protocol/perturbations/$p.yaml; [ "$p" = p3 ] && src=$OUT/draw/p3/perturbation.yaml
    if [ ! -e "$OUT/done/real_$p" ]; then
        rm -rf "$OUT/logs/real_$p" "$OUT/sealed/$p"
        isaac "python $HERE/twin_runs.py --ego ego.yaml --out $OUT/logs/real_$p --perturb $src --sealed $OUT/sealed/$p --seed $seed" > "$OUT/real_$p.log" 2>&1
        sys "python3 $HERE/bags.py convert $OUT/logs/real_$p" > "$OUT/bags_$p.log" 2>&1
        touch "$OUT/done/real_$p"
    fi
    seed=$((seed + 1))
    sys "python3 $HERE/fit_twin.py --logs $OUT/logs/real_$p --spec $OUT/roboracer.yaml --out $OUT/fit_$p.yaml" > "$OUT/fit_$p.log" 2>&1
    T=vehicle.axle_tires
    sys "python3 $HERE/refine_twin.py --logs $OUT/logs/real_$p --fitted $OUT/fit_$p.yaml --out $OUT/fit_${p}_stiffness.yaml --twin-cmd '$OUT/twin_eval_M5.sh {fitted} {out}' --only M5 --max-ay 2.0 --params $T.front.lat_stiff_value,$T.rear.lat_stiff_value --anchor 0 --max-evals 30" > "$OUT/refine_${p}_stiffness.log" 2>&1
    sys "python3 $HERE/refine_twin.py --logs $OUT/logs/real_$p --fitted $OUT/fit_${p}_stiffness.yaml --out $OUT/fit_${p}_refined.yaml --twin-cmd '$OUT/twin_eval_M6_M6b.sh {fitted} {out}' --only M6,M6b --params $T.front.tire_friction,$T.rear.tire_friction --anchor 0 --max-evals 30" > "$OUT/refine_${p}_friction.log" 2>&1
    for stage in fit_$p fit_${p}_refined; do
        isaac "python $HERE/twin_runs.py --ego ego.yaml --out $OUT/logs/twin_$stage --repetitions 1 --fitted $OUT/$stage.yaml" > "$OUT/twin_$stage.log" 2>&1
        sys "python3 $HERE/compare_runs.py $OUT/logs/real_$p $OUT/logs/twin_$stage --json $OUT/cmp_$stage.json" > "$OUT/cmp_$stage.txt" 2>&1 || true
    done
    sys "python3 $HERE/compare_runs.py $OUT/logs/real_$p $OUT/logs/twin0 --json $OUT/cmp_twin0_$p.json" > "$OUT/cmp_twin0_$p.txt" 2>&1 || true
    for stage in fit_$p fit_${p}_refined; do  # the sealed truth, read only now
        sys "python3 $HERE/check_recovery.py $OUT/sealed/$p/truth.yaml $OUT/$stage.yaml --logs $OUT/logs/real_$p" > "$OUT/recovery_$stage.txt" 2>&1 || true
    done
done
for f in "$OUT"/cmp_*.txt "$OUT"/recovery_*.txt; do echo "$(basename "$f"): $(tail -1 "$f")"; done
