#!/bin/bash
# Remove a gate's worktree (issue 191) once its commit has landed. `just gate-clean` runs it:
#
#     scripts/gate_clean.sh <commit> [--notag] [--dir <path>]
#
# The worktree is $SCENSIM_GATE_ROOT/gate-<sha8> (default /var/tmp/$USER), or `--dir`'s: one of
# this repository's registered worktrees whose HEAD is <commit> (a gate made with `just gate
# <commit> <dir>`); any other path is refused. It is removed only when nothing tracked changed
# in it and when either:
# - the commit is on an origin branch; or
# - it was gated before a rebase: every commit from its merge base with origin/main is
#   patch-equivalent to one on origin/main (`git cherry`: all "-"). Then the local tag
#   gate/<dir name> is set to it first, so the SHA a gate record cites stays reachable, and
#   printed. A tag of that name on another commit is refused. With `--notag` (`just gate-clean
#   <commit> notag=true`, for a user whose own go every tag needs) it tags nothing: the
#   worktree is kept, and the `git tag` command the user could run is printed.
# "Nothing tracked changed" allows a gate stopped during its submodule checkout: a submodule at
# its pin whose only changes are missing files (recursively), or with no HEAD yet, is an
# interrupted checkout, named and removed with the rest (nothing in it is anyone's edit).
# Otherwise the worktree is kept, saying why.
set -euo pipefail
usage="usage: scripts/gate_clean.sh <commit> [--notag] [--dir <path>]"
commit=${1:?$usage}
shift
notag=""
given=""
while [ $# -gt 0 ]; do
    case $1 in
        --notag) notag=1; shift ;;
        --dir) given=${2:?$usage}; shift 2 ;;
        *) echo "$usage"; exit 2 ;;
    esac
done
sha=$(git rev-parse --verify --quiet "$commit^{commit}") || { echo "$commit: not a commit here"; exit 1; }
if [ -n "$given" ]; then
    [ -d "$given" ] || { echo "no directory $given"; exit 1; }
    dir=$(cd "$given" && pwd -P)
    git worktree list --porcelain | grep -qxF "worktree $dir" \
        || { echo "$dir is not a worktree of this repository: refused"; exit 1; }
    head=$(git -C "$dir" rev-parse HEAD)
    [ "$head" = "$sha" ] || { echo "$dir is at $head, not $sha: refused"; exit 1; }
else
    dir="${SCENSIM_GATE_ROOT:-/var/tmp/${USER:-$(id -un)}}/gate-${sha:0:8}"
    [ -d "$dir" ] || { echo "no gate worktree at $dir"; exit 1; }
fi

# clean <repo dir> <its commit> <path prefix>: every tracked change in <repo dir> is a
# submodule's interrupted checkout (named on stdout); else "kept" with the change, and 1.
clean() {
    local d=$1 at=$2 pre=$3 line path entry pin sub top missing
    while IFS= read -r line; do
        path=${line:3}
        entry=$(git -C "$d" ls-tree "$at" -- "$path")
        if [ "${entry%% *}" != 160000 ]; then
            echo "$pre$path: a tracked change (${line:0:2}): kept"
            return 1
        fi
        pin=$(echo "$entry" | awk '{print $3}')
        sub="$d/$path"
        top=$(git -C "$sub" rev-parse --show-toplevel 2>/dev/null || true)
        if [ "$top" != "$(cd "$sub" 2>/dev/null && pwd -P)" ] \
                || ! git -C "$sub" rev-parse --verify --quiet HEAD > /dev/null; then
            echo "$pre$path: an interrupted checkout at ${pin:0:8}, not checked out at all"
            continue
        fi
        if [ "$(git -C "$sub" rev-parse HEAD)" != "$pin" ]; then
            echo "$pre$path: at $(git -C "$sub" rev-parse --short HEAD), not its pin ${pin:0:8}: kept"
            return 1
        fi
        missing=0
        while IFS= read -r l; do
            if git -C "$sub" ls-tree "$pin" -- "${l:3}" | grep -q '^160000 '; then
                clean "$sub" "$pin" "$pre$path/" || return 1
            elif [[ ${l:0:2} == "D " || ${l:0:2} == " D" || ${l:0:2} == "DD" ]]; then
                missing=$((missing + 1))
            else
                echo "$pre$path/${l:3}: a tracked change (${l:0:2}): kept"
                return 1
            fi
        done < <(git -C "$sub" status --porcelain --untracked-files=no)
        [ "$missing" -eq 0 ] || echo "$pre$path: an interrupted checkout at ${pin:0:8}, $missing files missing"
    done < <(git -C "$d" status --porcelain --untracked-files=no)
}
clean "$dir" "$sha" "" || { echo "$dir has tracked changes: kept"; exit 1; }
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
        echo "  git tag $tag $sha && just gate-clean $sha${given:+ dir=$dir}"
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
