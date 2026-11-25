#!/bin/bash
# The landing gate (issue 191): one commit, built and tested in a fresh worktree from a clean
# environment, the same for every peer. `just gate` runs it from a checkout:
#
#     scripts/gate.sh <commit> [<dir>]
#
# Steps: `just build`, `just test`, `just check`, each under `env -i` (HOME, USER, TERM, a fixed
# PATH, and ISAAC_ROOT when the host sets it). After each, `git status --porcelain
# --untracked-files=no` (no --ignore-submodules) must be empty. With ISAAC_ROOT set, `just
# test` must end saying the Isaac-Python lane ran (issue 186). The worktree is
# `$SCENSIM_GATE_ROOT/gate-<sha8>` unless <dir> names one; an existing path is refused. The
# output goes to <dir>/gate.log, and the summary line to stdout and <dir>/gate.txt:
#
#     gate ok <sha> tree <tree8> on <host> <time>: build test check clean; <Isaac lane>;
#         colcon-cargo-ros2 <v>; rustfmt <v>
#     gate FAILED <sha> at <step>: <reason>
#
# GATE_JUST (default `just`) and GATE_STEPS (default "build test check") are for the gate's
# own tests (scripts/test_gate.py), which run it against a stub.
set -euo pipefail
commit=${1:?usage: scripts/gate.sh <commit> [<dir>]}
JUST=${GATE_JUST:-just}
STEPS=${GATE_STEPS:-build test check}
top=$(git rev-parse --show-toplevel)
sha=$(git -C "$top" rev-parse --verify --quiet "$commit^{commit}") \
    || { echo "gate FAILED $commit at commit: not a commit here" >&2; exit 2; }
tree=$(git -C "$top" rev-parse "$sha^{tree}")
[ ${#sha} -eq 40 ] || { echo "gate FAILED $commit at commit: no 40-character sha" >&2; exit 2; }
root=${SCENSIM_GATE_ROOT:-/var/tmp/${USER:-$(id -un)}}
dir=${2:-$root/gate-${sha:0:8}}
if [ -e "$dir" ]; then
    echo "gate FAILED $sha at worktree: $dir exists (a gate never reuses a tree)" >&2
    exit 2
fi
mkdir -p "$(dirname "$dir")"
git -C "$top" worktree add -q --detach "$dir" "$sha"
cd "$dir" || exit 2
log="$dir/gate.log"
summary="$dir/gate.txt"
fail() {
    local line="gate FAILED $sha at $1: $2"
    echo "$line" | tee "$summary" >&2
    exit 1
}
[ "$(git rev-parse --show-toplevel)" = "$(cd "$dir" && pwd -P)" ] || fail worktree "not its own toplevel"
git submodule update -q --init --recursive >> "$log" 2>&1 || fail worktree "submodule update failed"
[ "$(git rev-parse HEAD)" = "$sha" ] || fail worktree "HEAD is not $sha"
[ "$(git rev-parse 'HEAD^{tree}')" = "$tree" ] || fail worktree "tree is not $tree"

clean=(env -i "HOME=$HOME" "USER=${USER:-$(id -un)}" TERM=dumb
       "PATH=$HOME/.cargo/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin")
[ -n "${ISAAC_ROOT:-}" ] && clean+=("ISAAC_ROOT=$ISAAC_ROOT")

status_clean() {
    local s
    s=$(git status --porcelain --untracked-files=no)
    echo "status after $1: [$s]" >> "$log"
    [ -z "$s" ] || fail "$1" "tracked changes after the step: $(echo "$s" | tr '\n' ';')"
}

echo "gate $sha tree $tree in $dir, $(date -Is)" >> "$log"
lane="Isaac lane: not on this host (ISAAC_ROOT unset)"
for step in $STEPS; do
    echo "== $step $(date -Is)" >> "$log"
    out="$dir/gate-$step.out"
    if ! "${clean[@]}" "$JUST" "$step" > "$out" 2>&1; then
        cat "$out" >> "$log"
        fail "$step" "\`just $step\` exited non-zero (last line: $(tail -1 "$out"))"
    fi
    cat "$out" >> "$log"
    status_clean "$step"
    if [ "$step" = test ]; then
        last=$(grep -E '^just test: done;' "$out" | tail -1 || true)
        if [ -n "${ISAAC_ROOT:-}" ]; then
            ran=$(echo "$last" | grep -oE 'Isaac-Python lane: ran \([0-9]+ tests' || true)
            [ -n "$ran" ] || fail test "ISAAC_ROOT is set but the Isaac-Python lane did not run (${last:-no summary line})"
            lane="Isaac lane ran (${ran##*(})"
        fi
    fi
    rm -f "$out"
done

ccr=$("${clean[@]}" python3 -c 'from importlib.metadata import version; print(version("colcon-cargo-ros2"))' 2>/dev/null || echo "?")
fmt=$("${clean[@]}" rustfmt +nightly --version 2>/dev/null | sed 's/^rustfmt //' || echo "?")
line="gate ok $sha tree ${tree:0:8} on $(hostname) $(date -Is): $STEPS clean; $lane; colcon-cargo-ros2 ${ccr:-?}; rustfmt ${fmt:-?}"
echo "$line" | tee "$summary"
echo "$line" >> "$log"
