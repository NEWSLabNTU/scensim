#!/usr/bin/env bash
# Roadmap 091 W20: f1tenth_system, unmodified, drives the RoboRacer example car on Isaac.
#
#     tools/w20_run.sh humble|jazzy OUT [DURATION_S]
#
# 1. The car: vehicles/roboracer.yaml's rig (aib.gen), the stand-in drive unit
#    component/roboracer_vesc behind aib's `vesc` vehicle interface, the planar lidar on /scan,
#    and ground truth on /ground_truth/odom, all made in OUT.
# 2. The field: fields/walled_room.usda, a 12 m x 8 m room. The car starts 1.5 m from the right
#    wall, heading along it.
# 3. The stack: f1tenth_stack's own nodes and config files (stack/roboracer_f1tenth's launch),
#    with the stand-in wall follower on `drive`. Humble runs here; jazzy runs in a container.
# 4. The verdict: tools/w20_watch.py, from outside the stack, into OUT/result_<distro>.json.
#
# The VESC's reported ERPM sign follows the branch: humble-devel's vesc_to_odom negates
# state.speed, jazzy-devel's does not (scensim issue 098), so the component's erpm_sign is -1
# for humble and +1 for jazzy. The frames are 20 Hz by default, as W20 was measured; since aib
# 79d68cd (issue 099) FRAME_RATE=40 gives /scan at the lidar's 40 Hz. Physics runs at 240 Hz
# (README, W7).
#
# Environment (host settings):
#   ISAAC_ROOT          Isaac Sim's install
#   F1TENTH_HUMBLE      f1tenth_system humble-devel's install (its setup.bash is sourced)
#   F1TENTH_JAZZY       f1tenth_system jazzy-devel's install, built in JAZZY_IMAGE
#   JAZZY_IMAGE         a docker image with ROS 2 Jazzy (for jazzy)
#   AIB                 an autoware_isaac_bridge checkout (default: this workspace's)
#   ROS_DOMAIN_ID       default 47
#   FRAME_RATE          default 20 (40: the lidar's own rate)
#   ISAAC_KIT_ARGS      Kit settings, e.g. one GPU on a host whose other is busy:
#                       "--/renderer/multiGpu/enabled=false --/renderer/activeGpu=0"
set -u
distro=${1:?usage: w20_run.sh humble|jazzy OUT [DURATION_S]}
OUT=${2:?usage: w20_run.sh humble|jazzy OUT [DURATION_S]}
dur=${3:-120}
case $distro in humble|jazzy) ;; *) echo "w20_run.sh: humble or jazzy, not $distro" >&2; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
WS=$(cd "$ROOT/../../.." && pwd)
AIB=${AIB:-$WS/src/autoware_isaac_bridge}
DOMAIN=${ROS_DOMAIN_ID:-47}
CY=$WS/src/scensim_launch/config/cyclonedds-localhost.xml
: "${ISAAC_ROOT:?ISAAC_ROOT: where Isaac Sim is installed}" "${F1TENTH_HUMBLE:?F1TENTH_HUMBLE: the install of f1tenth_system humble-devel}"
[ "$distro" = jazzy ] && : "${F1TENTH_JAZZY:?F1TENTH_JAZZY}" "${JAZZY_IMAGE:?JAZZY_IMAGE}"
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
humble() {  # the system's ROS 2 Humble with f1tenth_system
    env -i HOME="$HOME" PATH=/usr/bin:/bin bash -c "source /opt/ros/humble/setup.bash; source $F1TENTH_HUMBLE/setup.bash; export ROS_DOMAIN_ID=$DOMAIN RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$CY; $*"
}

# the car and the stack, built once per OUT
if [ ! -f "$OUT/roboracer.rig.yaml" ]; then
    cp "$ROOT/vehicles/roboracer.yaml" "$OUT/"
    env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONPATH="$AIB/src/aib" \
        bash -c "cd $OUT && python3 -m aib.gen --spec roboracer.yaml -o roboracer.rig.yaml" || exit 1
fi
if [ ! -d "$OUT/ws/install/roboracer_vesc" ]; then
    mkdir -p "$OUT/ws/src"
    cp -r "$ROOT/component/roboracer_vesc" "$ROOT/stack/roboracer_f1tenth" "$OUT/ws/src/"
    humble "cd $OUT/ws && colcon build" > "$OUT/build_humble.log" 2>&1 || { tail "$OUT/build_humble.log"; exit 1; }
fi
if [ "$distro" = jazzy ] && [ ! -d "$OUT/ws_jazzy/install/roboracer_f1tenth" ]; then
    mkdir -p "$OUT/ws_jazzy/src"
    cp -r "$ROOT/stack/roboracer_f1tenth" "$OUT/ws_jazzy/src/"
    docker run --rm --network host -u "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$F1TENTH_JAZZY:$F1TENTH_JAZZY:ro" -v "$OUT/ws_jazzy:$OUT/ws_jazzy" "$JAZZY_IMAGE" \
        bash -c "source /opt/ros/jazzy/setup.bash; source $F1TENTH_JAZZY/setup.bash; cd $OUT/ws_jazzy && colcon build" \
        > "$OUT/build_jazzy.log" 2>&1 || { tail "$OUT/build_jazzy.log"; exit 1; }
fi
sign=-1.0; [ "$distro" = jazzy ] && sign=1.0
site=$(ls -d "$OUT"/ws/install/roboracer_vesc/lib/python3*/site-packages)
cat > "$OUT/ego_$distro.yaml" <<EOF
# 091 W20: the RoboRacer example car, its stand-in drive unit behind the vesc interface
rig: $OUT/roboracer.rig.yaml
domain: $DOMAIN
node_name: isaac_vehicle
component:
  entry_point: roboracer_vesc
  # the VESC's reported ERPM sign that f1tenth_system $distro-devel reads (scensim issue 098)
  params: {erpm_sign: $sign}
  paths: [$site]
vehicle_interface: {profile: vesc}
ground_truth: {topic: /ground_truth/odom}
EOF

# the twin
setsid env -i HOME="$HOME" USER="$USER" PATH=/usr/local/bin:/usr/bin:/bin TERM=dumb \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI="file://$CY" ISAAC_ROOT="$ISAAC_ROOT" \
    ISAAC_KIT_ARGS="${ISAAC_KIT_ARGS:-}" \
    bash -c "source $AIB/src/aib/scripts/isaac_env.sh; export PYTHONPATH=$AIB/src/aib:\$PYTHONPATH; cd $AIB; exec python -m aib.runner --ego $OUT/ego_$distro.yaml --world $ROOT/fields/walled_room.usda --pose=-3,-2.5,0.05,0 --display '' --realtime --duration $((dur + 120)) --frame-rate ${FRAME_RATE:-20} --physics-dt 0.004166666666666667" \
    > "$OUT/ego_$distro.log" 2>&1 < /dev/null &
EP=$!
# the stack
ARGS="wheelbase:=0.33 speed:=1.5 max_steer:=0.36"
if [ "$distro" = humble ]; then
    setsid env -i HOME="$HOME" PATH=/usr/bin:/bin bash -c "source /opt/ros/humble/setup.bash; source $F1TENTH_HUMBLE/setup.bash; source $OUT/ws/install/setup.bash; export ROS_DOMAIN_ID=$DOMAIN RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$CY; ros2 launch roboracer_f1tenth f1tenth_twin.launch.py $ARGS" \
        > "$OUT/stack_$distro.log" 2>&1 < /dev/null &
    SP=$!
else
    name=w20-jazzy-$$
    setsid docker run --rm --name "$name" --network host --ipc host -u "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$F1TENTH_JAZZY:$F1TENTH_JAZZY:ro" -v "$OUT/ws_jazzy:$OUT/ws_jazzy:ro" -v "$(dirname "$CY"):/cfg:ro" \
        "$JAZZY_IMAGE" bash -c "source /opt/ros/jazzy/setup.bash; source $F1TENTH_JAZZY/setup.bash; source $OUT/ws_jazzy/install/setup.bash; export ROS_DOMAIN_ID=$DOMAIN RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file:///cfg/$(basename "$CY"); exec ros2 launch roboracer_f1tenth f1tenth_twin.launch.py $ARGS" \
        > "$OUT/stack_$distro.log" 2>&1 < /dev/null &
    SP=$!
fi
# the verdict
humble "python3 $HERE/w20_watch.py $dur $OUT/result_$distro.json" > "$OUT/watch_$distro.log" 2>&1
rc=$?
if [ "$distro" = humble ]; then kill -INT -"$SP" 2>/dev/null; sleep 3; kill -TERM -"$SP" 2>/dev/null
else docker kill -s INT "$name" > /dev/null 2>&1; sleep 5; docker stop -t 5 "$name" > /dev/null 2>&1; fi
kill -TERM -"$EP" 2>/dev/null
for _ in $(seq 30); do kill -0 "$EP" 2>/dev/null || break; sleep 2; done
kill -KILL -"$EP" 2>/dev/null   # Kit can ignore SIGTERM after a CUDA error
# the lidar's reads the twin dropped as short of a revolution (issue 099), into the result
python3 - "$OUT/ego_$distro.log" "$OUT/result_$distro.json" <<'PY'
import json, re, sys
m = re.findall(r"lidar (\S+): (\d+) read\(s\), (\d+) dropped short", open(sys.argv[1]).read())
r = json.load(open(sys.argv[2]))
r["lidar_reads"] = {n: {"reads": int(a), "dropped_short": int(b)} for n, a, b in m} or None
json.dump(r, open(sys.argv[2], "w"), indent=1)
PY
cat "$OUT/result_$distro.json"
exit $rc
