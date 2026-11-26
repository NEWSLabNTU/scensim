#!/bin/bash
# Remove a gate's worktree (issue 191) once its commit has landed. `just gate-clean` runs it:
#
#     scripts/gate_clean.sh <commit> [notag]
#
# The worktree is $SCENSIM_GATE_ROOT/gate-<sha8> (default /var/tmp/$USER). It is removed only
# when nothing tracked changed in it, and when either:
# - the commit is on an origin branch; or
# - it was gated before a rebase: every commit from its merge base with origin/main is
#   patch-equivalent to one on origin/main (`git cherry`: all "-"). Then the local tag
#   gate/<dir name> is set to it first, so the SHA a gate record cites stays reachable, and
#   printed. A tag of that name on another commit is refused. With `notag` (`just gate-clean
#   <commit> notag=true`, for a user whose own go every tag needs) it tags nothing: the
#   worktree is kept, and the `git tag` command the user could run is printed.
# Otherwise the worktree is kept, saying why.
set -euo pipefail
commit=${1:?usage: scripts/gate_clean.sh <commit> [notag]}
notag=${2:-}
sha=$(git rev-parse --verify --quiet "$commit^{commit}") || { echo "$commit: not a commit here"; exit 1; }
dir="${SCENSIM_GATE_ROOT:-/var/tmp/${USER:-$(id -un)}}/gate-${sha:0:8}"
[ -d "$dir" ] || { echo "no gate worktree at $dir"; exit 1; }
[ -z "$(git -C "$dir" status --porcelain --untracked-files=no)" ] || { echo "$dir has tracked changes: kept"; exit 1; }
git fetch -q origin
if [ -z "$(git branch -r --contains "$sha")" ]; then
    base=$(git merge-base "$sha" origin/main) || { echo "$sha shares no history with origin/main: kept"; exit 1; }
    cherry=$(git cherry origin/main "$sha" "$base")
    if [ -z "$cherry" ] || echo "$cherry" | grep -q '^+'; then
        echo "$sha is on no origin branch, nor all patch-equivalent on origin/main: kept"
        exit 1
    fi
    tag="gate/$(basename "$dir")"
    if [ -n "$notag" ]; then
        echo "$sha landed rebased (every commit patch-equivalent on origin/main), but notag:"
        echo "kept $dir; to tag the SHA its gate cites and then remove it, run:"
        echo "  git tag $tag $sha && just gate-clean $sha"
        exit 1
    fi
    if have=$(git rev-parse --verify --quiet "refs/tags/$tag^{commit}"); then
        [ "$have" = "$sha" ] || { echo "tag $tag is on $have, not $sha: kept"; exit 1; }
    else
        git tag "$tag" "$sha"
    fi
    echo "$sha landed rebased (every commit patch-equivalent on origin/main): tag $tag -> $sha"
fi
git worktree remove --force "$dir"
git worktree prune
echo "removed $dir"
