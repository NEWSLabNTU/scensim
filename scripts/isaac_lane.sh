#!/bin/bash
# scensim_isaac_world's, scensim_sampler's and scensim_batch's suites in Isaac's own Python,
# where the world server runs (issue 090), from a clean environment (isaac_env.sh: no system
# Humble in it). `just test` runs it from the repository's root:
#
#     scripts/isaac_lane.sh <status file>
#
# ISAAC_ROOT is a host setting: a gate's `env -i` passes it through (issue 186). Without an
# install there the lane does not run, and says so loudly: a banner on stderr, and the status
# file's one line, "NOT RUN: ...", which `just test` repeats as its last line; exit 0, so a host
# without Isaac still gates. When it runs, the status says how many tests ran; a failing suite
# fails the lane (its exit status), with "FAILED" in the status.
set -uo pipefail
status=${1:?usage: scripts/isaac_lane.sh <status file>}
LANE="the Isaac-Python lane (scensim_isaac_world, scensim_sampler, scensim_batch in Isaac's own Python)"
why=""
if [ -z "${ISAAC_ROOT:-}" ]; then
    why="ISAAC_ROOT unset"
elif [ ! -e "$ISAAC_ROOT/venv/bin/activate" ]; then
    why="ISAAC_ROOT=$ISAAC_ROOT, no venv/bin/activate"
fi
if [ -n "$why" ]; then
    line="NOT RUN: $LANE: $why"
    {
        echo "################################################################################"
        echo "# $line"
        echo "# (a host with an Isaac install passes ISAAC_ROOT into the gate's env -i; issue 186)"
        echo "################################################################################"
    } >&2
    echo "$line" > "$status"
    exit 0
fi
log=$(mktemp)
trap 'rm -f "$log"' EXIT
# the caller's CUDA_VISIBLE_DEVICES, when set (even empty: no GPU), passes through
pass=(HOME="$HOME" USER="$USER" PATH=/usr/bin:/bin ISAAC_ROOT="$ISAAC_ROOT")
[ -z "${CUDA_VISIBLE_DEVICES+set}" ] || pass+=(CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES")
env -i "${pass[@]}" bash -c '
    set -e
    source src/scensim_isaac_world/scripts/isaac_env.sh
    PYTHONNOUSERSITE=1 python3 -c "import numpy; print(\"numpy (Isaac):\", numpy.__version__, numpy.__file__)"
    PYTHONNOUSERSITE=1 python3 -m unittest discover -s src/scensim_isaac_world/test
    PYTHONNOUSERSITE=1 PYTHONPATH=src/scensim_sampler python3 -m unittest discover -s src/scensim_sampler/test
    PYTHONNOUSERSITE=1 python3 -m unittest discover -s src/scensim_batch/test
' 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
n=$(sed -n 's/^Ran \([0-9]*\) tests\{0,1\} in .*/\1/p' "$log" | awk '{t += $1} END {print t + 0}')
if [ "$rc" -eq 0 ]; then
    echo "Isaac-Python lane: ran ($n tests in 3 suites, OK)" > "$status"
else
    echo "FAILED: $LANE: exit $rc after $n tests" > "$status"
    echo "FAILED: $LANE: exit $rc" >&2
fi
exit "$rc"
