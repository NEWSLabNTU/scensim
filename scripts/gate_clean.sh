#!/bin/bash
# Remove a gate's worktree (issue 191) once its commit has landed. `just gate-clean` runs it:
#
#     scripts/gate_clean.sh <commit> [--notag] [--unlanded] [--dir <path>]
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
# - with `--unlanded` (`unlanded=true`), a commit on no origin branch: removed when a local
#   branch or tag other than gate/* holds it (named), so nothing is orphaned; no tag.
# "Nothing tracked changed" allows a gate stopped during its submodule checkout (see sub_ok):
# named and removed with the rest, with the ref that made it safe; nothing in it is anyone's
# edit. Otherwise the worktree is kept, saying why.
set -euo pipefail
usage="usage: scripts/gate_clean.sh <commit> [--notag] [--unlanded] [--dir <path>]"
commit=${1:?$usage}
shift
notag=""
unlanded=""
given=""
while [ $# -gt 0 ]; do
    case $1 in
        --notag) notag=1; shift ;;
        --unlanded) unlanded=1; shift ;;
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

# sub_ok <parent> <path> <pin> <prefix>: the submodule at <parent>/<path> is an interrupted
# checkout (named on stdout) or untouched; else "kept" with the change, and 1. Interrupted:
# - no HEAD, or not its own repository yet (a clone that never checked out);
# - at its pin, its only tracked changes deletions; a nested submodule (a gitlink in its tree)
#   is checked the same way, on its own (issue 191's sixth follow-up: the recursion used to
#   apply the superproject's rule to the parent's every file);
# - at another commit that one of its refs/remotes/* contains (a clone stopped before it moved
#   to the pin; no local commit), with deletions only: no modified, added or untracked file.
sub_ok() {
    local p=$1 path=$2 pin=$3 pre=$4 sub top head l npin onref="" untracked missing=0
    sub="$p/$path"
    top=$(git -C "$sub" rev-parse --show-toplevel 2>/dev/null || true)
    if [ "$top" != "$(cd "$sub" 2>/dev/null && pwd -P)" ] \
            || ! git -C "$sub" rev-parse --verify --quiet HEAD > /dev/null; then
        echo "$pre$path: an interrupted checkout at ${pin:0:8}, not checked out at all"
        return 0
    fi
    head=$(git -C "$sub" rev-parse HEAD)
    if [ "$head" != "$pin" ]; then
        onref=$(git -C "$sub" for-each-ref --contains "$head" --format='%(refname)' refs/remotes/ \
                | head -1)
        if [ -z "$onref" ]; then
            echo "$pre$path: at ${head:0:8}, not its pin ${pin:0:8}: kept"
            return 1
        fi
        untracked=$(git -C "$sub" status --porcelain --untracked-files=all | grep -m1 '^??' || true)
        if [ -n "$untracked" ]; then
            echo "$pre$path/${untracked:3}: untracked: kept"
            return 1
        fi
    fi
    while IFS= read -r l; do
        if npin=$(git -C "$sub" ls-tree "$head" -- "${l:3}" | awk '$1 == "160000" {print $3}') \
                && [ -n "$npin" ]; then
            sub_ok "$sub" "${l:3}" "$npin" "$pre$path/" || return 1
        elif [[ ${l:0:2} == "D " || ${l:0:2} == " D" || ${l:0:2} == "DD" ]]; then
            missing=$((missing + 1))
        else
            echo "$pre$path/${l:3}: a tracked change (${l:0:2}): kept"
            return 1
        fi
    done < <(git -C "$sub" status --porcelain --untracked-files=no)
    if [ -n "$onref" ]; then
        echo "$pre$path: an interrupted checkout at ${head:0:8} (on origin: $onref), not its pin" \
             "${pin:0:8}, $missing files missing"
    elif [ "$missing" -ne 0 ]; then
        echo "$pre$path: an interrupted checkout at ${pin:0:8}, $missing files missing"
    fi
}

# clean <dir> <commit>: the gate's own tracked files unchanged, and every submodule it lists
# sub_ok; else "kept" with the change, and 1.
clean() {
    local d=$1 at=$2 line path entry
    while IFS= read -r line; do
        path=${line:3}
        entry=$(git -C "$d" ls-tree "$at" -- "$path")
        if [ "${entry%% *}" != 160000 ]; then
            echo "$path: a tracked change (${line:0:2}): kept"
            return 1
        fi
        sub_ok "$d" "$path" "$(echo "$entry" | awk '{print $3}')" "" || return 1
    done < <(git -C "$d" status --porcelain --untracked-files=no)
}
clean "$dir" "$sha" || { echo "$dir has tracked changes: kept"; exit 1; }
git fetch -q origin
if [ -z "$(git branch -r --contains "$sha")" ]; then
    base=$(git merge-base "$sha" origin/main) || { echo "$sha shares no history with origin/main: kept"; exit 1; }
    cherry=$(git cherry origin/main "$sha" "$base")
    if [ -z "$cherry" ] || echo "$cherry" | grep -q '^+'; then
        if [ -z "$unlanded" ]; then
            echo "$sha is on no origin branch, nor all patch-equivalent on origin/main: kept" \
                 "(unlanded=true removes it when a local branch or tag holds $sha)"
            exit 1
        fi
        # only the main repository's branches and tags; never gate-clean's own gate/* tags
        keeper=$(git for-each-ref --contains "$sha" --format='%(refname)' refs/heads/ refs/tags/ \
                 | grep -v '^refs/tags/gate/' | head -1 || true)
        if [ -z "$keeper" ]; then
            echo "$sha is on no origin branch and in no local branch or tag (gate/* tags do not" \
                 "count): kept"
            exit 1
        fi
        git worktree remove --force "$dir"
        git worktree prune
        echo "removed $dir: $sha unlanded, kept by $keeper"
        exit 0
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
