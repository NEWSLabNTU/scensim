#!/usr/bin/env bash
# The simulation side on ROS 2 Jazzy (092 K6): this checkout's HEAD, in an Ubuntu 24.04 + Jazzy
# container, through a developer's own steps: `just setup`, `just build`, `just test`.
#
#   scripts/jazzy/check.sh            (`just jazzy-check`)
#
# It builds in a worktree of HEAD under build/jazzy-check (git-ignored), never in this
# checkout's build/ and install/, so a Humble workspace here is left as it is; commit first,
# what is not committed is not checked. The container (scripts/jazzy/Dockerfile, as a 24.04
# host is before `just setup`) runs as the caller's user, with CPUs and memory capped
# (JAZZY_CHECK_CPUS, default 8; JAZZY_CHECK_MEMORY, default 24g) and a home volume kept
# between runs (scensim-jazzy-home: rustup, cargo, pip). `just setup` runs in it every time:
# its apt packages live in the container, which is removed after the run. Its `just
# install-hooks` rewrites this repository's scensim hook stubs (the git dir is shared with the
# worktree), as `just setup` here would: the same stubs. Needs docker.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
WT=$ROOT/build/jazzy-check
IMAGE=scensim-jazzy-check
GIT_COMMON=$(cd "$ROOT" && cd "$(git rev-parse --git-common-dir)" && pwd)
command -v docker >/dev/null || { echo "jazzy-check: docker is not installed" >&2; exit 2; }

head=$(git -C "$ROOT" rev-parse HEAD)
[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ] \
    || echo "jazzy-check: uncommitted changes are not checked; checking HEAD $head" >&2
if [ -e "$WT" ]; then
    git -C "$ROOT" worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"
    git -C "$ROOT" worktree prune
fi
git -C "$ROOT" worktree add --detach -q "$WT" "$head"
git -C "$WT" submodule update -q --init --recursive

docker build -q -t "$IMAGE" --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" \
    "$ROOT/scripts/jazzy" >/dev/null
echo "jazzy-check: $head in $IMAGE (setup, build, test)"
# --init: an init that reaps orphans as PID 1, as on a host. Without it bash execs the last
# command, so `just` is PID 1 and never reaps; an orphaned stack stays a zombie, which still
# counts as a member of its process group, and t3's stop waited out every grace (test_t3's four
# stop tests timed out, 2026-11-24; issue 153, since fixed in t3 and scensim, which now count a
# group of zombies as gone). Kept: PID 1 reaps, as on a host, whatever else a test leaves.
docker run --rm --init --cpus "${JAZZY_CHECK_CPUS:-8}" --memory "${JAZZY_CHECK_MEMORY:-24g}" \
    --memory-swap "${JAZZY_CHECK_MEMORY:-24g}" \
    -v scensim-jazzy-home:/home/dev -v "$WT:$WT" -v "$GIT_COMMON:$GIT_COMMON" -w "$WT" \
    "$IMAGE" bash -c '
        set -e
        export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$PATH
        # just 1.40.0 or newer, as docs/development.md installs it
        if ! just --version 2>/dev/null | grep -qE "^just 1\.(4[0-9]|[5-9][0-9])"; then
            mkdir -p ~/.local/bin && rm -f ~/.local/bin/just
            curl --proto "=https" --tlsv1.2 -sSf https://just.systems/install.sh \
                | bash -s -- --tag 1.40.0 --to ~/.local/bin
        fi
        set +u; source /opt/ros/jazzy/setup.bash; set -u
        just setup
        just build
        just test'
echo "jazzy-check: $head passed on Jazzy"
