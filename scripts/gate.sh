#!/bin/bash
# The landing gate (issue 191): one commit, built and tested in a fresh worktree from a clean
# environment, the same for every peer. `just gate` runs it from a checkout:
#
#     scripts/gate.sh <commit> [<dir>]
#
# Steps: `just build`, `just test`, `just check`, each under `env -i` (HOME, USER, TERM, a fixed
# PATH) plus the host's settings: the calling checkout's `.env` copied into the worktree (just's
# dotenv-load reads it), and those of ISAAC_ROOT, SCENSIM_BUILD_JOBS, MAKEFLAGS,
# CARGO_BUILD_JOBS, COLCON_DEFAULTS_FILE and CUDA_VISIBLE_DEVICES the caller sets; the line
# names what it carried.
# GATE_WRAP=<command> runs every step under that command (a memory guard, say). After each, `git status --porcelain
# --untracked-files=no` (no --ignore-submodules) must be empty. With ISAAC_ROOT set, `just
# test` must end saying the Isaac-Python lane ran (issue 186). The worktree is
# `$SCENSIM_GATE_ROOT/gate-<sha8>` unless <dir> names one; an existing path is refused. The
# output goes to <dir>/gate.log, and the summary line to stdout and <dir>/gate.txt:
#
#     gate ok <sha> tree <tree8> on <host> <time>: build test check clean; <Isaac lane>;
#         colcon-cargo-ros2 <v>; rustfmt <v>; carried <.env and keys>[; under <GATE_WRAP>]
#     gate FAILED <sha> at <step>: <reason>
#
# A failed step's reason quotes its last line and, when there is one, its first rustfmt `Diff
# in` or compiler `error` line, which names the file.
#
# GATE_JUST (default `just`) and GATE_STEPS (default "build test check") are for the gate's
# own tests (scripts/test_gate.py), which run it against a stub.
set -euo pipefail
commit=${1:?usage: scripts/gate.sh <commit> [<dir>]}
JUST=${GATE_JUST:-just}
STEPS=${GATE_STEPS:-build test check}
CARRY="ISAAC_ROOT SCENSIM_BUILD_JOBS MAKEFLAGS CARGO_BUILD_JOBS COLCON_DEFAULTS_FILE CUDA_VISIBLE_DEVICES"
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
# the host's settings (CLAUDE.md: host settings are environment): the calling checkout's .env,
# which just's dotenv-load reads in the worktree, and an allow-list from the caller's own
carried=()
if [ -f "$top/.env" ]; then
    cp "$top/.env" "$dir/.env"
    carried+=(.env)
fi
for k in $CARRY; do
    if [ -n "${!k:-}" ]; then
        clean+=("$k=${!k}")
        carried+=("$k")
    fi
done
# GATE_WRAP: a command every step runs under (a memory guard, say), word-split
read -r -a wrap <<< "${GATE_WRAP:-}"
echo "gate: carried ${carried[*]:-nothing}${wrap[*]:+; each step under: ${wrap[*]}}" | tee -a "$log"

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
    # streamed into gate.log as it runs, so a long build can be watched (tail -f)
    if ! "${wrap[@]}" "${clean[@]}" "$JUST" "$step" 2>&1 | tee -a "$log" > "$out"; then
        # the first rustfmt `Diff in` or compiler `error` line names the file, the last
        # line is usually just's own `error: Recipe ... failed` (issue 191's follow-up)
        last=$(tail -1 "$out")
        first=$(grep -m1 -E '^(Diff in |error(\[E[0-9]+\])?: )' "$out" | sed "s|$dir/||g" || true)
        why="last line: $last"
        [ -n "$first" ] && [ "$first" != "$last" ] && why="$why; first: $first"
        fail "$step" "\`just $step\` exited non-zero ($why)"
    fi
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
line="gate ok $sha tree ${tree:0:8} on $(hostname) $(date -Is): $STEPS clean; $lane; colcon-cargo-ros2 ${ccr:-?}; rustfmt ${fmt:-?}; carried ${carried[*]:-nothing}${wrap[*]:+; under ${wrap[*]}}"
echo "$line" | tee "$summary"
echo "$line" >> "$log"
